import pytest
from tools import ToolError, dispatch


def test_type_phrasing_variants(toolbox):
    for phrase in ["air fryer", "air fryers", "Air Fryers", "blenders", "stick vacuums", "robot vacuum"]:
        r = dispatch(toolbox, "rank_products", {"metric": "reviews_new", "type": phrase, "limit": 3})
        assert r["count"] > 0, phrase


def test_unknown_type_lists_valid_values(toolbox):
    with pytest.raises(ToolError) as e:
        dispatch(toolbox, "rank_products", {"metric": "reviews_new", "type": "toaster pastry", "limit": 3})
    assert "Valid types" in str(e.value)


def test_refurbished_share_excludes_refurbished_only(toolbox):
    r = dispatch(toolbox, "rank_products", {"metric": "refurbished_share", "type": "air fryers", "limit": 5})
    assert all(x["reviews_new"] >= 20 for x in r["results"])
    assert r["definition"]
