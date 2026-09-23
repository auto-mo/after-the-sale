"""Deterministic, explainable pair scoring shared by the benchmark evaluation and SharkNinja resolution.

Layered decision (from explore/patterns/benchmarks.md):
  1. Model numbers agree (exact or one is a prefix of the other, >= 4 chars)  -> match, reason 'model'.
  2. Model numbers clearly conflict and titles are not near-identical         -> non-match, reason 'model_conflict'.
  3. Otherwise a weighted score of title overlap, model-in-other-title, price closeness and brand.
"""
import re

STOP = {"with", "and", "for", "the", "a", "an", "of", "in", "to", "&", "-", "by", "new", "renewed", "refurbished",
        "certified", "factory", "serviced", "black", "white", "silver", "gray", "grey", "red", "blue", "pink", "teal",
        "charcoal", "stainless", "steel", "edition", "version", "pack", "includes", "plus"}


def tokens(title_norm):
    return {t for t in (title_norm or "").split() if t not in STOP and len(t) > 1}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def model_relation(ma, mb):
    if not ma or not mb:
        return "missing"
    if ma == mb:
        return "equal"
    short, long_ = sorted((ma, mb), key=len)
    if len(short) >= 4 and long_.startswith(short):
        return "prefix"
    # Retailer prefixes/suffixes around the same core code (ver97185 vs 97185, 70gh012000003 vs gh012000003).
    if len(short) >= 5 and short in long_ and re.search(r"\d{3}", short):
        return "contains"
    return "conflict"


NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:gb|tb|mb|qt|quart|oz|w|watt|cup|inch|in|mm|mp|x)?\b")


def numbers(title_norm):
    return {re.sub(r"\s", "", n) for n in NUM_RE.findall(title_norm or "")}


def price_sim(pa, pb):
    if not pa or not pb or pa <= 0 or pb <= 0:
        return None
    return min(pa, pb) / max(pa, pb)


DEFAULT_W = dict(jac=1.0, cross=0.35, price=0.25, brand=0.1, num=0.3)


def score_pair(a, b, w=DEFAULT_W):
    """a, b: dicts with title_norm, model_no, title_model_tokens (list), price, brand.
    Returns (score 0-1, reason, features)."""
    ta, tb = tokens(a.get("title_norm")), tokens(b.get("title_norm"))
    jac = jaccard(ta, tb)
    rel = model_relation(a.get("model_no"), b.get("model_no"))
    # Strict: one side's model code appears in the other side's title.
    strict = bool((a.get("model_no") and a["model_no"] in set(b.get("title_model_tokens") or []))
                  or (b.get("model_no") and b["model_no"] in set(a.get("title_model_tokens") or [])))
    cross = strict or bool(set(a.get("title_model_tokens") or []) & set(b.get("title_model_tokens") or []))
    na, nb = numbers(a.get("title_norm")), numbers(b.get("title_norm"))
    num_mismatch = bool(na and nb and not (na & nb))
    ps = price_sim(a.get("price"), b.get("price"))
    brand = a.get("brand") and b.get("brand") and a["brand"] == b["brand"]
    f = dict(jaccard=round(jac, 3), model_relation=rel, model_cross=cross, model_in_title=strict,
             num_mismatch=num_mismatch, price_sim=None if ps is None else round(ps, 3), brand_eq=bool(brand))
    if rel in ("equal", "prefix", "contains"):
        return 1.0, "model_" + rel, f
    if rel == "conflict":
        # Sibling variants (NV350 vs NV352) have near-identical titles; only a model code found in the
        # other title overrides a genuine conflict.
        return (0.9, "model_in_other_title", f) if strict else (0.0, "model_conflict", f)
    parts, wsum = [w["jac"] * jac, w["cross"] * cross, w["brand"] * bool(brand)], w["jac"] + w["cross"] + w["brand"]
    if ps is not None:
        parts.append(w["price"] * ps)
        wsum += w["price"]
    return max(0.0, sum(parts) / wsum - w.get("num", 0) * num_mismatch), "blended", f
