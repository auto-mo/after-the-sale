"""Flask app for the After the Sale chat service.

GET  /api/health  -> {ok, mode, model, budget_left_usd}
POST /api/chat     -> {reply, view, tools, limited, paused, message}

Same-origin only (no CORS headers). The Anthropic API key never leaves this process:
it is read from env, never logged, never included in any response.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from config import Config, load_config
from limits import BudgetLedger, RateLimiter, client_ip
from llm import AnthropicLLM, MockLLM
from tools import build_toolbox

MAX_BODY_BYTES = 32 * 1024
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
logger = logging.getLogger("after_the_sale")


def verify_turnstile(token: str | None, secret: str, remote_ip: str | None = None) -> bool:
    """Verify a Cloudflare Turnstile token server-side. Real network call in production;
    tests monkeypatch this function so no network access is needed to exercise the path."""
    if not token:
        return False
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(TURNSTILE_VERIFY_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return bool(payload.get("success"))
    except Exception:
        return False


def create_app(cfg: Config | None = None) -> Flask:
    cfg = cfg or load_config()

    app = Flask(__name__)
    app.config["DEMAND_EVIDENCE_CONFIG"] = cfg

    toolbox = build_toolbox(cfg.data_dir)
    ledger = BudgetLedger(cfg.ledger_path, cfg.daily_budget_usd)
    rate_limiter = RateLimiter(cfg.rate_per_hour)

    def make_llm():
        if cfg.llm_mode == "anthropic":
            return AnthropicLLM(
                toolbox=toolbox,
                api_key=cfg.anthropic_api_key,
                model=cfg.model,
                max_reply_tokens=cfg.max_reply_tokens,
                max_tool_rounds=cfg.max_tool_rounds,
            )
        return MockLLM(toolbox=toolbox)

    app.config["DEMAND_EVIDENCE_LEDGER"] = ledger
    app.config["DEMAND_EVIDENCE_RATE_LIMITER"] = rate_limiter
    app.config["DEMAND_EVIDENCE_TOOLBOX"] = toolbox
    app.config["DEMAND_EVIDENCE_MAKE_LLM"] = make_llm

    # -----------------------------------------------------------------
    # Static serving (dev convenience)
    # -----------------------------------------------------------------
    if cfg.serve_static:

        @app.route("/", defaults={"path": "index.html"})
        @app.route("/<path:path>")
        def serve_web(path):
            web_dir = Path(cfg.web_dir)
            full = (web_dir / path).resolve()
            if not str(full).startswith(str(web_dir.resolve())):
                return "Not found", 404
            if full.is_dir() or not full.exists():
                return send_from_directory(str(web_dir), "index.html")
            return send_from_directory(str(web_dir), path)

    # -----------------------------------------------------------------
    # GET /api/health
    # -----------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "ok": True,
                "mode": cfg.llm_mode,
                "model": cfg.model,
                "budget_left_usd": round(ledger.budget_left(), 4),
            }
        )

    # -----------------------------------------------------------------
    # POST /api/chat
    # -----------------------------------------------------------------
    @app.route("/api/chat", methods=["POST"])
    def chat():
        start = time.monotonic()

        content_length = request.content_length or 0
        if content_length > MAX_BODY_BYTES:
            return jsonify({"error": "Request body too large."}), 400

        raw = request.get_data(cache=False, as_text=False)
        if len(raw) > MAX_BODY_BYTES:
            return jsonify({"error": "Request body too large."}), 400

        if not request.is_json:
            return jsonify({"error": "Request must be JSON."}), 400
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return jsonify({"error": "Request body must be valid JSON."}), 400
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        messages = payload.get("messages")
        view_in = payload.get("view")
        turnstile_token = payload.get("turnstile_token")

        err = _validate_messages(messages, cfg)
        if err:
            return jsonify({"error": err}), 400

        # Invite code gate.
        if cfg.invite_code:
            if request.headers.get("X-Invite-Code") != cfg.invite_code:
                return jsonify({"error": "Missing or invalid invite code."}), 400

        # Rate limit.
        ip = client_ip(request.headers, request.remote_addr)
        ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
        if not rate_limiter.allow(ip):
            return (
                jsonify({"limited": True, "message": "You have sent a lot of messages. Please wait a bit and try again."}),
                429,
            )

        # Turnstile gate: required on the first message of a conversation.
        user_message_count = sum(1 for m in messages if m.get("role") == "user")
        is_first_message = user_message_count == 1
        if cfg.turnstile_secret and is_first_message:
            if not verify_turnstile(turnstile_token, cfg.turnstile_secret, ip):
                return jsonify({"error": "Verification failed. Please retry."}), 400

        # Budget gate.
        if ledger.is_paused():
            logger.info(
                json.dumps(
                    {
                        "ts": time.time(),
                        "ip_hash": ip_hash,
                        "paused": True,
                        "latency_ms": round((time.monotonic() - start) * 1000, 1),
                    }
                )
            )
            return jsonify(
                {
                    "reply": "",
                    "view": None,
                    "tools": [],
                    "limited": False,
                    "paused": True,
                    "message": "The assistant has reached today's limit. It will be back tomorrow; the rest of the tool still works.",
                }
            )

        llm = app.config["DEMAND_EVIDENCE_MAKE_LLM"]()
        result = llm.run(messages, view_in)

        spent = ledger.add_cost(result.cost.usd(cfg.price_in_per_mtok, cfg.price_out_per_mtok))

        logger.info(
            json.dumps(
                {
                    "ts": time.time(),
                    "ip_hash": ip_hash,
                    "input_tokens": result.cost.input_tokens,
                    "output_tokens": result.cost.output_tokens,
                    "cache_read_tokens": result.cost.cache_read_tokens,
                    "cache_creation_tokens": result.cost.cache_creation_tokens,
                    "tools": [t["name"] for t in result.tools_used],
                    "spent_today_usd": round(spent, 4),
                    "latency_ms": round((time.monotonic() - start) * 1000, 1),
                }
            )
        )

        return jsonify(
            {
                "reply": result.reply,
                "view": result.view,
                "tools": result.tools_used,
                "limited": False,
                "paused": False,
                "message": None,
            }
        )

    return app


def _validate_messages(messages, cfg: Config) -> str | None:
    if not isinstance(messages, list) or not messages:
        return "messages must be a non-empty list."
    if len(messages) > cfg.max_turns * 2:
        return f"Too many messages (max {cfg.max_turns} user turns)."

    user_turns = 0
    expected = "user"
    for m in messages:
        if not isinstance(m, dict) or "role" not in m or "content" not in m:
            return "Each message must have role and content."
        role = m["role"]
        content = m["content"]
        if role not in ("user", "assistant"):
            return "Message role must be 'user' or 'assistant'."
        if role != expected:
            return "Message roles must alternate, starting with 'user'."
        expected = "assistant" if role == "user" else "user"
        if not isinstance(content, str):
            return "Message content must be a string."
        if len(content) > cfg.max_message_chars:
            return f"Message content exceeds {cfg.max_message_chars} characters."
        if role == "user":
            user_turns += 1

    if messages[-1]["role"] != "user":
        return "The conversation must end with a user message."
    if user_turns > cfg.max_turns:
        return f"Too many user turns (max {cfg.max_turns})."
    return None


if __name__ == "__main__":
    app = create_app()
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5055")), debug=False)
