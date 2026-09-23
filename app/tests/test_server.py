import json

from tests.conftest import make_config


def test_health_no_secrets(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert "budget_left_usd" in body
    dumped = json.dumps(body)
    assert "sk-ant" not in dumped
    assert "ANTHROPIC_API_KEY" not in dumped


def test_chat_end_to_end_sets_view(client):
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "show the AF101 from January 2019 to June 2019"}]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["paused"] is False
    assert body["limited"] is False
    assert body["view"] is not None
    assert body["view"]["product_id"] == "SN-AF101"
    assert body["view"]["from"] == "2019-01"
    assert body["view"]["to"] == "2019-06"
    assert any(t["name"] == "set_view" for t in body["tools"])


def test_chat_ranking_intent_calls_rank_tool(client):
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "which products are the most refurbished"}]},
    )
    body = resp.get_json()
    assert resp.status_code == 200
    assert any(t["name"] == "rank_products" for t in body["tools"])


def test_chat_rejects_non_json(client):
    resp = client.post("/api/chat", data="not json", content_type="text/plain")
    assert resp.status_code == 400


def test_chat_rejects_malformed_json(client):
    resp = client.post("/api/chat", data="{not valid", content_type="application/json")
    assert resp.status_code == 400


def test_chat_rejects_empty_messages(client):
    resp = client.post("/api/chat", json={"messages": []})
    assert resp.status_code == 400


def test_chat_rejects_missing_messages(client):
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 400


def test_chat_rejects_non_alternating_roles(client):
    resp = client.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "user", "content": "hi again"},
            ]
        },
    )
    assert resp.status_code == 400


def test_chat_rejects_ending_in_assistant(client):
    resp = client.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        },
    )
    assert resp.status_code == 400


def test_chat_rejects_overlong_message(cfg, client):
    long_text = "a" * (cfg.max_message_chars + 1)
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": long_text}]})
    assert resp.status_code == 400


def test_chat_rejects_too_many_turns(cfg, client):
    messages = []
    for _ in range(cfg.max_turns + 1):
        messages.append({"role": "user", "content": "hi"})
        messages.append({"role": "assistant", "content": "hello"})
    messages.append({"role": "user", "content": "hi"})
    resp = client.post("/api/chat", json={"messages": messages})
    assert resp.status_code == 400


def test_chat_rejects_oversized_body(client):
    huge = "a" * (33 * 1024)
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": huge[:900]}], "padding": huge})
    assert resp.status_code == 400


def test_rate_limit_returns_429(tmp_path):
    from server import create_app

    cfg = make_config(tmp_path, rate_per_hour=2)
    app = create_app(cfg)
    c = app.test_client()
    for _ in range(2):
        resp = c.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
        assert resp.status_code == 200
    resp = c.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert resp.status_code == 429
    body = resp.get_json()
    assert body["limited"] is True


def test_budget_cap_pauses_without_calling_model(tmp_path):
    from server import create_app

    cfg = make_config(tmp_path, daily_budget_usd=0.0)
    app = create_app(cfg)
    c = app.test_client()
    resp = c.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["paused"] is True
    assert body["reply"] == ""
    assert "limit" in body["message"].lower()


def test_invite_code_required(tmp_path):
    from server import create_app

    cfg = make_config(tmp_path, invite_code="letmein")
    app = create_app(cfg)
    c = app.test_client()
    resp = c.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert resp.status_code == 400

    resp2 = c.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers={"X-Invite-Code": "letmein"},
    )
    assert resp2.status_code == 200


def test_turnstile_required_on_first_message(tmp_path, monkeypatch):
    from server import create_app
    import server as server_module

    cfg = make_config(tmp_path, turnstile_secret="secret123")
    app = create_app(cfg)
    c = app.test_client()

    monkeypatch.setattr(server_module, "verify_turnstile", lambda token, secret, ip=None: False)
    resp = c.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}], "turnstile_token": "bad"})
    assert resp.status_code == 400

    monkeypatch.setattr(server_module, "verify_turnstile", lambda token, secret, ip=None: True)
    resp2 = c.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}], "turnstile_token": "good"})
    assert resp2.status_code == 200


def test_turnstile_not_required_on_later_messages(tmp_path, monkeypatch):
    from server import create_app
    import server as server_module

    cfg = make_config(tmp_path, turnstile_secret="secret123")
    app = create_app(cfg)
    c = app.test_client()
    monkeypatch.setattr(server_module, "verify_turnstile", lambda token, secret, ip=None: True)

    resp = c.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hello"}], "turnstile_token": "good"},
    )
    assert resp.status_code == 200

    # Second turn (3 messages, ending in user) should not require turnstile again.
    monkeypatch.setattr(server_module, "verify_turnstile", lambda token, secret, ip=None: False)
    resp2 = c.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
                {"role": "user", "content": "another question"},
            ]
        },
    )
    assert resp2.status_code == 200


def test_static_serving_flag(tmp_path):
    from server import create_app

    cfg = make_config(tmp_path, serve_static=True)
    app = create_app(cfg)
    c = app.test_client()
    resp = c.get("/data/products.json")
    assert resp.status_code == 200


def test_static_serving_disabled_by_default(client):
    resp = client.get("/data/products.json")
    assert resp.status_code == 404
