import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest

from config import Config
from server import create_app

REPO_ROOT = APP_DIR.parent
DATA_DIR = REPO_ROOT / "data" / "clean"
WEB_DIR = REPO_ROOT / "web"


def make_config(tmp_path, **overrides) -> Config:
    defaults = dict(
        anthropic_api_key=None,
        llm_mode="mock",
        model="claude-haiku-4-5",
        daily_budget_usd=3.0,
        price_in_per_mtok=1.0,
        price_out_per_mtok=5.0,
        rate_per_hour=20,
        max_turns=12,
        max_message_chars=1000,
        max_reply_tokens=800,
        max_tool_rounds=5,
        turnstile_secret=None,
        invite_code=None,
        ledger_path=tmp_path / "ledger.json",
        serve_static=False,
        data_dir=DATA_DIR,
        web_dir=WEB_DIR,
    )
    defaults.update(overrides)
    return Config(**defaults)


@pytest.fixture
def cfg(tmp_path):
    return make_config(tmp_path)


@pytest.fixture
def app(cfg):
    return create_app(cfg)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def toolbox(cfg):
    from tools import build_toolbox

    return build_toolbox(cfg.data_dir)
