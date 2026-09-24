import pytest

from tools import ToolError, dispatch


def test_find_products_basic(toolbox):
    r = toolbox.find_products(query="air fryer", limit=3)
    assert r["count"] <= 3
    assert all("product_id" in m for m in r["matches"])


def test_find_products_model_code(toolbox):
    r = toolbox.find_products(query="AF101", limit=5)
    assert any(m["product_id"] == "SN-AF101" for m in r["matches"])


def test_find_products_excludes_accessories_by_default(toolbox):
    r = toolbox.find_products(query="filter", limit=10)
    assert all(m["is_accessory"] is False for m in r["matches"])


def test_find_products_bad_input(toolbox):
    with pytest.raises(ToolError):
        toolbox.find_products(query="")


def test_find_products_limit_clamped(toolbox):
    r = toolbox.find_products(query="ninja", limit=999)
    assert r["count"] <= 10


def test_get_product_timeline_both_channels(toolbox):
    r = toolbox.get_product_timeline("SN-AF101", channel="both")
    assert r["data_complete_through"] == "2023-03"
    assert "new" in r["totals"] and "renewed" in r["totals"]
    # Totals come from the full range (regression: refurbished total was cut to 4 of 10 by a shared row cap).
    assert r["totals"]["new"]["reviews"] == 5877
    assert r["totals"]["renewed"]["reviews"] == 10
    assert {x["channel"] for x in r["rows"]} == {"new", "renewed"}
    assert sum(x["reviews"] for x in r["rows"] if x["channel"] == "renewed") == 10


def test_get_product_timeline_clamps_to_2023_09(toolbox):
    r = toolbox.get_product_timeline("SN-AF101", to="2030-01", channel="new")
    def last_month(period):
        if "-Q" in period:
            y, q = period.split("-Q")
            return f"{y}-{int(q) * 3:02d}"
        return period
    assert all(last_month(m["period"]) <= "2023-09" for m in r["rows"])


def test_get_product_timeline_bad_product(toolbox):
    with pytest.raises(ToolError):
        toolbox.get_product_timeline("NOT-A-PRODUCT")


def test_get_product_timeline_bad_channel(toolbox):
    with pytest.raises(ToolError):
        toolbox.get_product_timeline("SN-AF101", channel="sideways")


def test_get_product_complaints(toolbox):
    r = toolbox.get_product_complaints("SN-S3501")
    top = r["new_units"]["top_complaints"]
    assert top and all(t["label"] and 0 <= t["share_of_low_star"] <= 1 for t in top)
    assert [t["share_of_low_star"] for t in top] == sorted((t["share_of_low_star"] for t in top), reverse=True)
    assert r["type_average_peer_brands"]["low_star_reviews"] > 0
    assert any(y["year"] == 2022 for y in r["by_year"])
    assert "never failure rates" in r["how_to_read"]


def test_get_product_complaints_bad_product(toolbox):
    with pytest.raises(ToolError):
        toolbox.get_product_complaints("NOT-A-PRODUCT")


def test_compare_product_type(toolbox):
    r = toolbox.compare_product_type("coffee makers")
    assert r["product_type"] == "coffee maker" and "Keurig" in r["peer_brands"]
    assert len(r["largest_gaps_vs_peers"]) == 3
    b = toolbox.compare_product_type("blenders")  # peers have too few blender reviews: SharkNinja only
    assert b["peer_brands"] is None and b["top_complaints_sharkninja"] and "SharkNinja" in b["stated_time_to_failure"]


def test_rank_products_reviews_new(toolbox):
    r = toolbox.rank_products(metric="reviews_new", limit=5)
    values = [x["value"] for x in r["results"]]
    assert values == sorted(values, reverse=True)
    assert len(r["results"]) <= 5


def test_rank_products_refurbished_share(toolbox):
    r = toolbox.rank_products(metric="refurbished_share", limit=5, min_reviews=10)
    for x in r["results"]:
        assert 0 <= x["value"] <= 1


def test_rank_products_complaint_share(toolbox):
    r = toolbox.rank_products(metric="complaint_share", type="robot vacuum", theme="app", limit=5)
    assert r["results"] and all(x["product_type"] == "vacuum-robot" for x in r["results"])
    assert "App and connection" in r["definition"]
    with pytest.raises(ToolError):
        toolbox.rank_products(metric="complaint_share", theme="teleportation")


def test_rank_products_rating_change_sorted_by_fall(toolbox):
    vals = [x["value"] for x in toolbox.rank_products(metric="rating_change", limit=5)["results"]]
    assert vals == sorted(vals) and vals[0] < 0


def test_rank_products_bad_metric(toolbox):
    with pytest.raises(ToolError):
        toolbox.rank_products(metric="not_a_metric")


def test_rank_products_limit_clamped(toolbox):
    r = toolbox.rank_products(metric="reviews_new", limit=999)
    assert len(r["results"]) <= 10


def test_get_findings(toolbox):
    r = toolbox.get_findings()
    life = r["ratings_over_product_life"]
    assert set(life) == {"SharkNinja", "Peers"} and life["SharkNinja"]["mean_change"] < 0
    assert r["refurbished_vs_new_same_product_same_year"]["cells"] > 0
    assert "none survives" in r["not_detectable"]
    assert len(r["limits"]) >= 3 and any("not failure" in x for x in r["limits"])


def test_search_reviews_basic(toolbox):
    r = toolbox.search_reviews("SN-AF101", limit=5)
    assert r["matching_count"] >= 0
    excerpts = r["untrusted_reviews"]["excerpts"]
    assert len(excerpts) <= 5
    for e in excerpts:
        assert len(e["text"]) <= 350


def test_search_reviews_rating_filter(toolbox):
    r = toolbox.search_reviews("SN-AF101", max_rating=2, limit=15)
    for e in r["untrusted_reviews"]["excerpts"]:
        assert e["rating"] <= 2


def test_search_reviews_bad_product(toolbox):
    with pytest.raises(ToolError):
        toolbox.search_reviews("NOT-A-PRODUCT")


def test_search_reviews_bad_channel(toolbox):
    with pytest.raises(ToolError):
        toolbox.search_reviews("SN-AF101", channel="sideways")


def test_search_reviews_limit_clamped(toolbox):
    r = toolbox.search_reviews("SN-AF101", limit=999)
    assert len(r["untrusted_reviews"]["excerpts"]) <= 15


def test_set_view_defaults(toolbox):
    r = toolbox.set_view("SN-AF101")
    v = r["view"]
    assert v["product_id"] == "SN-AF101"
    assert v["to"] <= "2023-09"
    assert v["channels"]
    assert v["measure"] == "rating"  # the page contract is volume | rating; rating is the default


def test_set_view_clamps_future_to(toolbox):
    r = toolbox.set_view("SN-AF101", from_="2000-01", to="2099-01")
    v = r["view"]
    assert v["to"] <= "2023-09"
    assert v["from"] >= "2018-01"  # AF101 didn't exist before ~2018


def test_set_view_bad_product(toolbox):
    with pytest.raises(ToolError):
        toolbox.set_view("NOT-A-PRODUCT")


def test_set_view_channel_default_nonempty(toolbox):
    r = toolbox.set_view("SN-AF101", channels=["not-a-channel"])
    assert r["view"]["channels"]


def test_dispatch_maps_from_keyword(toolbox):
    r = dispatch(toolbox, "get_product_timeline", {"product_id": "SN-AF101", "from": "2019-01"})
    assert all(m["period"][:4] >= "2019" for m in r["rows"])
    assert r["totals"]["new"]["reviews"] < 5877


def test_dispatch_unknown_tool(toolbox):
    with pytest.raises(ToolError):
        dispatch(toolbox, "delete_everything", {})


def test_search_reviews_theme_and_helpful_sort(toolbox):
    r = toolbox.search_reviews("SN-S3501", theme="no steam", max_rating=2, sort="helpful", limit=5)
    ex = r["untrusted_reviews"]["excerpts"]
    assert ex and all(e["rating"] <= 2 for e in ex)
    votes = [e["helpful_votes"] for e in ex]
    assert votes == sorted(votes, reverse=True)
    with pytest.raises(ToolError):
        toolbox.search_reviews("SN-S3501", theme="x; DROP TABLE sn_review")
