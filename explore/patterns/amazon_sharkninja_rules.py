"""
Reusable DuckDB SQL fragments / regex rules derived from the pattern-discovery pass over
data/raw/amazon2023/meta_sharkninja.jsonl and reviews_sharkninja.jsonl.

This is READ-ONLY diagnostic code. It does not touch data/raw/. Nothing here writes files
or calls any network/LLM API. Run with `.venv/bin/python`.

See explore/patterns/amazon_sharkninja.md for the full write-up, counts, and rationale
behind each rule.
"""

import duckdb
import re

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
META_PATH = f"{ROOT}/data/raw/amazon2023/meta_sharkninja.jsonl"
REVIEWS_PATH = f"{ROOT}/data/raw/amazon2023/reviews_sharkninja.jsonl"


def connect() -> duckdb.DuckDBPyConnection:
    """Open a fresh DuckDB connection with meta/reviews views registered."""
    con = duckdb.connect()
    con.execute(
        f"CREATE VIEW meta_raw AS SELECT *, row_number() over () as rid "
        f"FROM read_json_auto('{META_PATH}', maximum_object_size=20000000)"
    )
    con.execute(f"CREATE VIEW reviews AS SELECT * FROM read_json_auto('{REVIEWS_PATH}')")
    con.execute(
        """
        CREATE VIEW meta AS
        SELECT
          rid, parent_asin, title, store, main_category, average_rating, rating_number,
          price, categories, features, description, details, images, videos,
          regexp_replace(map_extract(details,'Item model number')[1]::VARCHAR, '^"|"$', '', 'g') AS d_item_model_number,
          regexp_replace(map_extract(details,'Model Name')[1]::VARCHAR, '^"|"$', '', 'g') AS d_model_name,
          regexp_replace(map_extract(details,'Part Number')[1]::VARCHAR, '^"|"$', '', 'g') AS d_part_number,
          regexp_replace(map_extract(details,'Brand')[1]::VARCHAR, '^"|"$', '', 'g') AS d_brand,
          regexp_replace(map_extract(details,'Manufacturer')[1]::VARCHAR, '^"|"$', '', 'g') AS d_manufacturer,
          regexp_replace(map_extract(details,'Brand Name')[1]::VARCHAR, '^"|"$', '', 'g') AS d_brand_name,
          regexp_replace(map_extract(details,'Style')[1]::VARCHAR, '^"|"$', '', 'g') AS d_style,
          regexp_replace(map_extract(details,'Color')[1]::VARCHAR, '^"|"$', '', 'g') AS d_color,
          regexp_replace(map_extract(details,'Capacity')[1]::VARCHAR, '^"|"$', '', 'g') AS d_capacity,
          regexp_replace(map_extract(details,'Wattage')[1]::VARCHAR, '^"|"$', '', 'g') AS d_wattage,
          regexp_replace(map_extract(details,'Date First Available')[1]::VARCHAR, '^"|"$', '', 'g') AS d_date_first_avail,
          map_extract(details,'Best Sellers Rank')[1] AS d_bsr
        FROM meta_raw
        """
    )
    return con


# ---------------------------------------------------------------------------
# Section 1: model number extraction order
# ---------------------------------------------------------------------------
# Priority order to fill model_no for a listing (first non-null wins):
#   1. details['Item model number']   (1,353 / 2,012 = 67.2% coverage, cleanest source)
#   2. parenthetical token in title:  \(([A-Z]{1,4}[0-9]{2,5}[A-Za-z0-9]{0,4})\)
#      (recovers 65 more listings that have no Item model number at all -> 70.5% combined)
#   3. bare model-like token anywhere in title (last resort, noisier):
#      \b[A-Z]{1,3}[0-9]{2,5}[A-Z]{0,4}[0-9]{0,3}\b
#      (matches something in 471 of the remaining rows, but includes false positives like
#       stray dimension/measurement tokens - needs a stoplist and manual spot-check before
#       trusting it for linking)
# details['Model Name'] and details['Style'] are NOT reliable primary sources: they are
# frequently full marketing strings ("Ninja FG551 Indoor Grill Air Fryer") rather than a
# bare model code, and disagree with Item model number in 284/1353 = 21% of rows where
# both are present (usually Model Name is the more verbose one).
ITEM_MODEL_NUMBER_CLEAN_SQL = (
    "regexp_replace(map_extract(details,'Item model number')[1]::VARCHAR, '^\"|\"$', '', 'g')"
)

TITLE_PAREN_MODEL_REGEX = r"\(([A-Z]{1,4}[0-9]{2,5}[A-Za-z0-9]{0,4})\)"
TITLE_BARE_MODEL_REGEX = r"\b([A-Z]{1,3}[0-9]{2,5}[A-Z]{0,4}[0-9]{0,3})\b"


def extract_model_no(item_model_number: str | None, title: str) -> tuple[str | None, str]:
    """Python mirror of the proposed extraction order. Returns (model_no, source)."""
    if item_model_number:
        return item_model_number.strip().upper(), "details.Item model number"
    m = re.search(TITLE_PAREN_MODEL_REGEX, title)
    if m:
        return m.group(1).upper(), "title parenthetical"
    m = re.search(TITLE_BARE_MODEL_REGEX, title)
    if m:
        return m.group(1).upper(), "title bare (low confidence)"
    return None, "none"


# ---------------------------------------------------------------------------
# Section 2: base_model / retailer-suffix collapse rule
# ---------------------------------------------------------------------------
# Known confirmed retailer suffix in THIS dataset: "AMZ" (11 listings, e.g. HE402AMZ,
# IX144AMZ, BL770AMZ, CH963AMZ, AMZ493BRN, S3504AMZ, HV343AMZ, HS152AMZ, AMZ012BL).
# "AMZ" can appear as a suffix (HE402AMZ) OR fused as a prefix/infix in a multi-token
# code (AMZ493BRN, AMZE1SRKHZ2002BK) - so a simple "$" suffix strip under-collapses it;
# treat AMZ as a token to strip anywhere, not just at the end.
# WM/BRN/Q/C/CO/REF/RB are single/double letter codes that recur as trailing tokens after
# the numeric core and plausibly denote color/retailer/condition variants of the same base
# unit. Q and C are the most frequent trailing single letters (Q=31, C=4 in this corpus;
# also Z=23, H=17, A=16 - many of THOSE are legitimate parts of the base code, not suffixes,
# so do not strip them blindly - see risk note below).
BASE_MODEL_SQL = (
    "regexp_replace(upper({col}), '(AMZ|WM|BRN|COST|TGT|REF|RB|CO|Q|C)+$', '')"
)

# Risk: stripping a single trailing letter is not safe for every family. Example measured
# in this corpus: base "CF080" merges CF080, CF080Q, CF080REF (3 distinct raw model
# numbers, 6 listings) - all really are the same Ninja Coffee Bar unit, so that collapse is
# safe. But letters like Z, H, A, D appear as load-bearing parts of a base code (e.g. "IZ662H",
# "RV851WV") rather than as a variant suffix, so a blanket strip-last-letter rule is too
# aggressive; only strip the specific token set above (Q, C, CO, REF, RB, WM, BRN, COST, TGT,
# AMZ), never a bare single letter class.


# ---------------------------------------------------------------------------
# Section 3: Renewed listings
# ---------------------------------------------------------------------------
RENEWED_TITLE_PATTERNS = [
    r"(?i)\(Renewed\)",
    r"(?i)Certified Refurbished",
    r"(?i)Factory Serviced",
    r"(?i)\bRefurb\b",
]


# ---------------------------------------------------------------------------
# Section 5: product_type classification (title + category fallback)
# ---------------------------------------------------------------------------
PRODUCT_TYPE_CASE_SQL = """
CASE
 WHEN title ILIKE '%air fryer%' THEN 'air fryer'
 WHEN title ILIKE '%blender%' OR title ILIKE '%nutri ninja%' THEN 'blender'
 WHEN title ILIKE '%robot%' AND title ILIKE '%vacuum%' THEN 'robot vacuum'
 WHEN title ILIKE '%stick vacuum%' OR title ILIKE '%rocket%' THEN 'vacuum-stick'
 WHEN title ILIKE '%upright%' OR title ILIKE '%navigator%' OR title ILIKE '%rotator%' THEN 'vacuum-upright'
 WHEN title ILIKE '%steam mop%' OR title ILIKE '%steam pocket mop%' THEN 'steam mop'
 WHEN title ILIKE '%coffee%' THEN 'coffee maker'
 WHEN title ILIKE '%grill%' THEN 'grill'
 WHEN title ILIKE '%pressure cook%' OR title ILIKE '%foodi%' THEN 'pressure cooker'
 WHEN title ILIKE '%creami%' OR title ILIKE '%ice cream%' THEN 'ice cream maker'
 WHEN title ILIKE '%air purif%' THEN 'air purifier'
 WHEN title ILIKE '%food processor%' THEN 'food processor'
 WHEN title ILIKE '%vacuum%' THEN 'vacuum-other'
 WHEN title ILIKE '%replacement%' OR title ILIKE '%compatible%' OR title ILIKE '%for shark%'
      OR title ILIKE '%for ninja%' OR title ILIKE '%filter%' OR title ILIKE '%part%'
      OR title ILIKE '%accessory%' THEN 'accessory/part'
 ELSE 'unclassified'
END
"""
# Measured: 1,632/2,012 (81%) classified by title keywords alone; 380 fall to
# 'unclassified' - most of those ARE classifiable, just need a categories[] fallback
# (e.g. categories ends in 'Slow Cookers', 'Toaster Ovens', 'Mixers', 'Deep Fryers',
# 'Dinnerware & Serveware' for a mis-titled accessory). Recommend: apply this title rule
# first, then fall back to `categories[array_length(categories)]` (last category segment)
# for anything still 'unclassified' before giving up.


# ---------------------------------------------------------------------------
# Section 6: unit normalization
# ---------------------------------------------------------------------------
def capacity_to_quarts(raw: str | None) -> float | None:
    """Normalize a details['Capacity'] string to quarts. 1 US quart = 32 fl oz = 0.946353 L."""
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"^([\d.]+)\s*Quarts?$", raw, re.I)
    if m:
        return float(m.group(1))
    m = re.match(r"^([\d.]+)\s*Fluid Ounces?$", raw, re.I)
    if m:
        return float(m.group(1)) / 32.0
    m = re.match(r"^([\d.]+)\s*Ounces?$", raw, re.I)
    if m:
        return float(m.group(1)) / 32.0
    m = re.match(r"^([\d.]+)\s*Liters?$", raw, re.I)
    if m:
        return float(m.group(1)) / 0.946353
    m = re.match(r"^([\d.]+)\s*Milliliters?$", raw, re.I)
    if m:
        return float(m.group(1)) / 946.353
    m = re.match(r"^([\d.]+)\s*Cups?$", raw, re.I)
    if m:
        return float(m.group(1)) / 4.0
    # 'Pounds' is a weight, not a volume - do NOT convert; keep as a separate weight field.
    return None


def wattage_to_watts(raw: str | None) -> float | None:
    if not raw:
        return None
    m = re.match(r"^([\d.]+)\s*[Ww]atts?$", raw.strip())
    if m:
        return float(m.group(1))
    m = re.match(r"^([\d.]+)\.00$", raw.strip())
    if m:
        return float(m.group(1))
    return None


TITLE_QT_REGEX = r"(?i)([0-9]+(?:\.[0-9]+)?)[- ]?(?:Qt|Quart)"
TITLE_WATT_REGEX = r"(?i)([0-9]+)[- ]?(?:Watt|W)\b"
TITLE_OZ_REGEX = r"(?i)([0-9]+(?:\.[0-9]+)?)[- ]?(?:Oz|Ounce)"


if __name__ == "__main__":
    con = connect()
    print(con.execute("SELECT store, count(*) FROM meta GROUP BY 1 ORDER BY 2 DESC").fetchall())
