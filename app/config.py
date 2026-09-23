"""Configuration for the Demand Evidence chat service.

Everything is loaded from environment variables (via `app/.env` in dev). Nothing is
hard-coded. See app/.env.example for the full list of variables and placeholder values.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# app/ is the package directory; the repo root is its parent.
APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent

# Load app/.env if present. Does not override already-set environment variables.
load_dotenv(APP_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return int(val)


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return float(val)


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY") or None)
    llm_mode: str = field(default_factory=lambda: os.environ.get("LLM_MODE", "mock").strip().lower())
    model: str = field(default_factory=lambda: os.environ.get("MODEL", "claude-haiku-4-5"))

    daily_budget_usd: float = field(default_factory=lambda: _env_float("DAILY_BUDGET_USD", 3.0))
    price_in_per_mtok: float = field(default_factory=lambda: _env_float("PRICE_IN_PER_MTOK", 1.0))
    price_out_per_mtok: float = field(default_factory=lambda: _env_float("PRICE_OUT_PER_MTOK", 5.0))

    rate_per_hour: int = field(default_factory=lambda: _env_int("RATE_PER_HOUR", 20))
    max_turns: int = field(default_factory=lambda: _env_int("MAX_TURNS", 12))
    max_message_chars: int = field(default_factory=lambda: _env_int("MAX_MESSAGE_CHARS", 1000))
    max_reply_tokens: int = field(default_factory=lambda: _env_int("MAX_REPLY_TOKENS", 800))
    max_tool_rounds: int = field(default_factory=lambda: _env_int("MAX_TOOL_ROUNDS", 5))

    turnstile_secret: str | None = field(default_factory=lambda: os.environ.get("TURNSTILE_SECRET") or None)
    invite_code: str | None = field(default_factory=lambda: os.environ.get("INVITE_CODE") or None)

    ledger_path: Path = field(
        default_factory=lambda: Path(os.environ.get("LEDGER_PATH") or str(APP_DIR / ".ledger.json"))
    )

    serve_static: bool = field(default_factory=lambda: _env_bool("SERVE_STATIC", False))

    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("DATA_DIR") or str(ROOT_DIR / "data" / "clean"))
    )
    web_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("WEB_DIR") or str(ROOT_DIR / "web"))
    )

    def validate(self) -> None:
        if self.llm_mode not in ("mock", "anthropic"):
            raise RuntimeError(f"LLM_MODE must be 'mock' or 'anthropic', got {self.llm_mode!r}")
        if self.llm_mode == "anthropic" and not self.anthropic_api_key:
            raise RuntimeError(
                "LLM_MODE=anthropic requires ANTHROPIC_API_KEY to be set. Refusing to start."
            )


def load_config() -> Config:
    cfg = Config()
    cfg.validate()
    return cfg
