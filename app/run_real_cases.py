#!/usr/bin/env python3
"""Run app/real_api_cases.json against the real Claude API and check expectations.

DO NOT RUN THIS during the build described in the project's build instructions — no
API key is available yet and no call to the real Anthropic API is permitted during
that build. The owner runs this later, once a key is supplied, e.g.:

    ANTHROPIC_API_KEY=sk-ant-... LLM_MODE=anthropic \
        .venv/bin/python app/run_real_cases.py --max-usd 0.50

It loads each case's conversation, runs it through AnthropicLLM (the same manual tool
loop the live server uses), and mechanically checks:
  - must_call: every named tool appears in the tools actually used.
  - must_set_view: whether a view was set matches the expectation.
  - must_not_contain: none of the given substrings (case-insensitive) appear in the reply.

Stops immediately (without running further cases) once cumulative cost exceeds --max-usd.
Prints a pass/fail line per case, then a summary with total tokens and total cost.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from config import load_config  # noqa: E402
from llm import AnthropicLLM  # noqa: E402
from tools import build_toolbox  # noqa: E402


def check_case(case: dict, reply: str, tools_used: list[dict], view: dict | None) -> tuple[bool, list[str]]:
    expect = case["expect"]
    problems = []

    called_names = {t["name"] for t in tools_used}
    for name in expect.get("must_call", []):
        if name not in called_names:
            problems.append(f"expected tool {name!r} to be called; got {sorted(called_names)}")

    must_set_view = expect.get("must_set_view")
    if must_set_view is not None:
        did_set_view = view is not None
        if did_set_view != must_set_view:
            problems.append(f"expected must_set_view={must_set_view}, got view={'set' if did_set_view else 'not set'}")

    low_reply = (reply or "").lower()
    for phrase in expect.get("must_not_contain", []):
        if phrase.lower() in low_reply:
            problems.append(f"reply must not contain {phrase!r}")

    return (len(problems) == 0, problems)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-usd", type=float, default=0.50, help="Stop once cumulative cost exceeds this.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=APP_DIR / "real_api_cases.json",
        help="Path to the cases JSON file.",
    )
    args = parser.parse_args()

    cfg = load_config()
    if cfg.llm_mode != "anthropic":
        print("Refusing to run: set LLM_MODE=anthropic and a real ANTHROPIC_API_KEY first.", file=sys.stderr)
        return 2

    cases = json.loads(args.cases.read_text())
    toolbox = build_toolbox(cfg.data_dir)

    total_input = total_output = total_cache_read = total_cache_write = 0
    total_cost = 0.0
    n_pass = n_fail = 0

    for case in cases:
        if total_cost > args.max_usd:
            print(f"\nStopping: cumulative cost ${total_cost:.4f} exceeded --max-usd {args.max_usd:.2f}.")
            break

        llm = AnthropicLLM(
            toolbox=toolbox,
            api_key=cfg.anthropic_api_key,
            model=cfg.model,
            max_reply_tokens=cfg.max_reply_tokens,
            max_tool_rounds=cfg.max_tool_rounds,
        )
        result = llm.run(case["messages"], case.get("view"))

        cost_usd = result.cost.usd(cfg.price_in_per_mtok, cfg.price_out_per_mtok)
        total_cost += cost_usd
        total_input += result.cost.input_tokens
        total_output += result.cost.output_tokens
        total_cache_read += result.cost.cache_read_tokens
        total_cache_write += result.cost.cache_creation_tokens

        ok, problems = check_case(case, result.reply, result.tools_used, result.view)
        status = "PASS" if ok else "FAIL"
        if ok:
            n_pass += 1
        else:
            n_fail += 1
        print(f"[{status}] {case['id']}  (${cost_usd:.4f}, tools={[t['name'] for t in result.tools_used]})")
        if not ok:
            for p in problems:
                print(f"       - {p}")
            print(f"       reply: {result.reply[:300]!r}")

    print("\n--- summary ---")
    print(f"pass={n_pass} fail={n_fail}")
    print(f"tokens: input={total_input} output={total_output} cache_read={total_cache_read} cache_write={total_cache_write}")
    print(f"total cost: ${total_cost:.4f}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
