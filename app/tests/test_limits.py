from limits import BudgetLedger, RateLimiter, client_ip


def test_rate_limiter_allows_up_to_limit():
    rl = RateLimiter(per_hour=3)
    assert rl.allow("ip1")
    assert rl.allow("ip1")
    assert rl.allow("ip1")
    assert not rl.allow("ip1")


def test_rate_limiter_keys_are_independent():
    rl = RateLimiter(per_hour=1)
    assert rl.allow("ip1")
    assert rl.allow("ip2")
    assert not rl.allow("ip1")


def test_client_ip_precedence():
    assert client_ip({"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "2.2.2.2"}, "3.3.3.3") == "1.1.1.1"
    assert client_ip({"X-Forwarded-For": "2.2.2.2, 9.9.9.9"}, "3.3.3.3") == "2.2.2.2"
    assert client_ip({}, "3.3.3.3") == "3.3.3.3"
    assert client_ip({}, None) == "unknown"


def test_budget_ledger_starts_at_zero(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json", daily_budget_usd=1.0)
    assert ledger.spent_today() == 0.0
    assert not ledger.is_paused()
    assert ledger.budget_left() == 1.0


def test_budget_ledger_accumulates_and_pauses(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json", daily_budget_usd=1.0)
    ledger.add_cost(0.4)
    assert abs(ledger.spent_today() - 0.4) < 1e-9
    assert not ledger.is_paused()
    ledger.add_cost(0.7)
    assert ledger.is_paused()
    assert ledger.budget_left() == 0.0


def test_budget_ledger_persists_across_instances(tmp_path):
    path = tmp_path / "ledger.json"
    BudgetLedger(path, daily_budget_usd=5.0).add_cost(1.5)
    ledger2 = BudgetLedger(path, daily_budget_usd=5.0)
    assert abs(ledger2.spent_today() - 1.5) < 1e-9
