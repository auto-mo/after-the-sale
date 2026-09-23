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


def test_schemas_use_only_strict_supported_keywords():
    # Strict tool schemas reject numeric/string range keywords (found in the first real-API run: HTTP 400).
    from tools import TOOL_SCHEMAS
    banned = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength", "maxLength", "pattern"}

    def walk(node):
        if isinstance(node, dict):
            assert not (banned & set(node)), node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for t in TOOL_SCHEMAS:
        walk(t["input_schema"])


def test_house_style_removes_em_dashes():
    from llm import _house_style
    assert "—" not in _house_style("review counts — ratings—and text")
