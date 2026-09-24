from limits import CostBreakdown
from llm import MockLLM


def test_mock_llm_show_command_sets_view(toolbox):
    llm = MockLLM(toolbox)
    result = llm.run(
        [{"role": "user", "content": "show the AF101 from January 2019 to June 2019"}], None
    )
    assert result.view is not None
    assert result.view["product_id"] == "SN-AF101"
    assert result.view["from"] == "2019-01"
    assert result.view["to"] == "2019-06"
    assert any(t["name"] == "set_view" for t in result.tools_used)


def test_mock_llm_show_command_channel_filter(toolbox):
    llm = MockLLM(toolbox)
    result = llm.run(
        [{"role": "user", "content": "open the AF101 from January 2019 to June 2019, new units only"}],
        None,
    )
    assert result.view["channels"] == ["new"]


def test_mock_llm_ranking(toolbox):
    llm = MockLLM(toolbox)
    result = llm.run([{"role": "user", "content": "which products are the most refurbished"}], None)
    assert any(t["name"] == "rank_products" for t in result.tools_used)
    assert result.reply


def test_mock_llm_complain(toolbox):
    llm = MockLLM(toolbox)
    result = llm.run([{"role": "user", "content": "what do people complain about the AF101"}], None)
    assert any(t["name"] == "get_product_complaints" for t in result.tools_used)
    assert "1 and 2-star" in result.reply


def test_mock_llm_compare_with_peers(toolbox):
    llm = MockLLM(toolbox)
    result = llm.run([{"role": "user", "content": "compare shark upright vacuums with peers"}], None)
    assert any(t["name"] == "compare_product_type" for t in result.tools_used)
    assert "peers" in result.reply


def test_mock_llm_fake_costs_are_nonzero(toolbox):
    llm = MockLLM(toolbox)
    result = llm.run([{"role": "user", "content": "hello there"}], None)
    assert result.cost.input_tokens > 0
    assert result.cost.output_tokens > 0


def test_cost_breakdown_usd_formula():
    c = CostBreakdown(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000, cache_creation_tokens=1_000_000)
    usd = c.usd(price_in_per_mtok=1.0, price_out_per_mtok=5.0)
    # 1.0 (input) + 5.0 (output) + 0.10 (cache read @ 10%) + 1.25 (cache write @ 125%)
    assert abs(usd - (1.0 + 5.0 + 0.10 + 1.25)) < 1e-9


def test_house_style_drops_speculation_sentences():
    from llm import _house_style
    out = _house_style("No steam rose in 2022. The timing suggests a production change. Worth checking what changed.\n"
                       "- Quality control or manufacturing changes around that time\n- Refurbished arrival problems")
    assert "production" not in out and "manufacturing" not in out
    assert "No steam rose in 2022." in out and "Worth checking what changed." in out and "Refurbished" in out
