"""
Reusable normalization + matching-signal functions derived from the benchmark
diagnosis in explore/patterns/benchmarks.md.

Read-only diagnostic code. No network calls, no LLM calls. Depends only on
the Python standard library so it can be imported from a notebook or a
DuckDB Python UDF without extra installs.
"""
import re
import string

MISSING_TOKENS = {"", "nan", "none", "null", "n/a", "na"}


def is_missing(val):
    """True if a raw string field should be treated as missing."""
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in MISSING_TOKENS


def parse_price(val):
    """
    Parse a raw price string into a float, or None if unparseable/missing.
    Handles: '$1,299.99', '1299.99', '1,299', ranges ('12.99 - 15.99' -> mean),
    trailing text ('19.99 USD'), and the literal string 'nan'.
    """
    if is_missing(val):
        return None
    s = str(val).strip()
    # strip currency symbols and letters, keep digits, dot, comma, dash, space
    s2 = re.sub(r"[^\d.,\-\s]", "", s)
    # range like "12.99 - 15.99" or "12.99-15.99"
    range_match = re.match(r"^\s*([\d.,]+)\s*-\s*([\d.,]+)\s*$", s2)
    if range_match:
        try:
            a = float(range_match.group(1).replace(",", ""))
            b = float(range_match.group(2).replace(",", ""))
            return (a + b) / 2.0
        except ValueError:
            return None
    s3 = s2.replace(",", "").strip()
    # collapse multiple numbers separated by space (e.g. "1 299.99" edge case) -> remove spaces
    s3 = s3.replace(" ", "")
    if s3 in ("", "-", "."):
        return None
    try:
        return float(s3)
    except ValueError:
        return None


_MODEL_STRIP_RE = re.compile(r"[\s\-_/]+")


def normalize_modelno(val):
    """
    Normalize a model-number field for equality comparison:
    lowercase, strip, remove spaces/hyphens/underscores/slashes.
    'NST-400MX-S2' -> 'nst400mxs2'; 'CR249-TA' -> 'cr249ta'; 'HD-PXT1TU2 / B' -> 'hdpxt1tu2b'
    Returns None if missing.
    """
    if is_missing(val):
        return None
    s = str(val).strip().lower()
    s = _MODEL_STRIP_RE.sub("", s)
    return s if s else None


_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_text(val):
    """Lowercase, strip punctuation, collapse whitespace. For title/name Jaccard."""
    if is_missing(val):
        return ""
    s = str(val).lower().translate(_PUNCT_TABLE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(val):
    return set(normalize_text(val).split())


def jaccard(a_tokens, b_tokens):
    if not a_tokens and not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return inter / union if union else 0.0


# A token counts as a candidate "model code" if it mixes letters and digits,
# or is a long alphanumeric run, and is not a pure unit/measurement word.
_MODEL_TOKEN_RE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9\-/]{4,}$", re.IGNORECASE)
_UNIT_SUFFIX_RE = re.compile(
    r"^\d+(\.\d+)?(gb|tb|mb|mp|hz|ghz|mm|cm|in|inch|ft|oz|lb|lbs|w|v|hr|hrs|hour|hours|pack|ct|pc|pcs)$",
    re.IGNORECASE,
)


def extract_model_tokens(title):
    """
    Extract candidate model-number-like tokens from a free-text title.
    Returns a set of normalized (compacted, lowercased) tokens.
    """
    if is_missing(title):
        return set()
    raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/]*", str(title))
    out = set()
    for tok in raw_tokens:
        if _UNIT_SUFFIX_RE.match(tok):
            continue
        if _MODEL_TOKEN_RE.match(tok):
            norm = _MODEL_STRIP_RE.sub("", tok.lower())
            if len(norm) >= 4:
                out.add(norm)
    return out


def modelno_in_title(modelno_norm, title_tokens_norm):
    """modelno_norm: normalized modelno string. title_tokens_norm: set of normalized model tokens from the other title."""
    if not modelno_norm:
        return False
    return modelno_norm in title_tokens_norm


BRAND_ALIASES = {
    "hp": "hp",
    "hewlett packard": "hp",
    "hewlett-packard": "hp",
    "hewlettpackard": "hp",
}


def normalize_brand(val):
    if is_missing(val):
        return None
    s = str(val).strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None
    return BRAND_ALIASES.get(s, s)


def relative_price_diff(p1, p2):
    """|p1-p2| / max(p1,p2). None if either price missing or both zero."""
    if p1 is None or p2 is None:
        return None
    denom = max(p1, p2)
    if denom == 0:
        return None
    return abs(p1 - p2) / denom
