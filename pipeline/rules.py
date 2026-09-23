"""Deterministic cleaning rules. Promoted from explore/patterns/*_rules.py and tightened after
spot checks (see PLAN.md, Phase 3). Pure functions: no I/O."""
import re
import string

MISSING = {"", "nan", "none", "null", "n/a", "na", "#n/a", "unknown"}


def is_missing(v):
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return str(v).strip().lower() in MISSING


def clean_str(v):
    return None if is_missing(v) else re.sub(r"\s+", " ", str(v).replace("\xa0", " ")).strip()


def parse_price(v):
    if is_missing(v):
        return None
    s = re.sub(r"[^\d.,\-]", "", str(v))
    rng = re.match(r"^([\d.,]+)-([\d.,]+)$", s)
    try:
        if rng:
            return round((float(rng.group(1).replace(",", "")) + float(rng.group(2).replace(",", ""))) / 2, 2)
        s = s.replace(",", "")
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


# ---------------- model numbers ----------------
# SharkNinja codes: 1-4 letters, 2-5 digits, optional alphanumeric tail (AF101, NV356E, IZ662H, AF150AMZ, CS970QSS, RV1001AE).
MODEL_RE = re.compile(r"\b([A-Z]{1,4}\d{2,5}[A-Z0-9]{0,6})\b")
# Part numbers used on accessories: digits-letters-digits (1244FC500, 134KKW300) or long all-digit codes.
PART_RE = re.compile(r"\b(\d{3,4}[A-Z]{2,4}\d{3}[A-Z]?|X[A-Z0-9]{5,10}|\d{5,10})\b")
# Tokens that fit MODEL_RE but are not models.
MODEL_STOP = {"USB2", "USB3", "HEPA13", "H13", "H11", "H12", "UV5", "PM25", "PM2", "CO2", "AA10"}
COMPAT_RE = re.compile(r"(?i)\b(for|compatible with|compatible|fits|works with|replacement for|replaces)\b")
IMN_NOISE_RE = re.compile(r"(?i)\(?factory serviced\)?|\brenewed\b|\bseries\b|[®™]|\bshark\b|\bninja\b")


def norm_model(tok):
    return re.sub(r"[^A-Z0-9]", "", tok.upper()) if tok else None


def model_tokens(text):
    if not text:
        return []
    up = text.upper()
    out = []
    for t in MODEL_RE.findall(up):
        # ASINs (B0xxxxxxxx) sometimes sit in the model field; they are listing IDs, not models.
        if t not in MODEL_STOP and not re.fullmatch(r"B0[0-9A-Z]{8}", t):
            out.append(t)
    return list(dict.fromkeys(out))


def part_tokens(text):
    return list(dict.fromkeys(PART_RE.findall(text.upper()))) if text else []


def extract_model(item_model_number, title, is_accessory):
    """Return (model_no, source, confidence, compatible_models, part_no, candidates).

    Rules, first match wins:
      1. details['Item model number'] after stripping noise, if it holds exactly one model code.
      2. Title code in brackets, e.g. '(IX141)'.
      3. Title codes before any 'for / compatible with / fits' phrase. One distinct code -> model;
         several -> first code, lower confidence.
    For accessories, codes after a 'for ...' phrase are compatible models, not identity.
    """
    title = clean_str(title) or ""
    head, tail = title, ""
    m = COMPAT_RE.search(title)
    if m:
        head, tail = title[: m.start()], title[m.end():]
    compatible = model_tokens(tail) if (is_accessory or m) else []
    part = (part_tokens(item_model_number or "") or part_tokens(title) or [None])[0]

    # A model named explicitly in the title ("(BL205)", "Model BL205") beats a conflicting details field.
    explicit = re.findall(r"\(([A-Z]{1,4}\d{2,5}[A-Z0-9]{0,6})\)|\bMODEL[:#]?\s+([A-Z]{1,4}\d{2,5}[A-Z0-9]{0,6})\b", title.upper())
    explicit = [a or b for a, b in explicit if (a or b) not in MODEL_STOP]
    imn = clean_str(item_model_number)
    if imn:
        toks = model_tokens(IMN_NOISE_RE.sub(" ", imn))
        if explicit and toks and not is_accessory and not any(core_model(e) == core_model(t) for e in explicit for t in toks):
            return explicit[0], "title_explicit_over_details", "high", compatible, part, explicit + toks
        if len(toks) == 1:
            return toks[0], "details", "high", compatible, part, toks
        if len(toks) > 1:
            return None, "details_ambiguous", "none", compatible or toks, part, toks
        if part and is_accessory:
            return None, "details_part_only", "none", compatible, part, []

    if is_accessory:
        return None, "accessory_no_model", "none", compatible or model_tokens(title), part, []

    br = re.findall(r"\(([A-Z]{1,4}\d{2,5}[A-Z0-9]{0,6})\)", title.upper())
    br = [b for b in br if b not in compatible]
    if br:
        return br[0], "title_bracket", "high", compatible, part, br

    toks = [t for t in model_tokens(head) if t not in compatible]
    if is_accessory and not toks:
        return None, "accessory_no_model", "none", compatible, part, []
    if len(toks) == 1:
        return toks[0], "title", "medium", compatible, part, toks
    if len(toks) > 1:
        return toks[0], "title_first_of_many", "low", compatible, part, toks
    return None, "none", "none", compatible, part, []


# Retailer / condition / colour suffixes. AMZ is always stripped (confirmed Amazon-exclusive code).
# The rest are stripped only when a sibling model shares the stripped base (checked in clean.py).
AMZ_RE = re.compile(r"AMZ$")
SUFFIX_RE = re.compile(r"(Q|C|CO|REF|RB|WM|BRN|COST|TGT|QSS|BK|WH|GR)$")


# ---------------- product type ----------------
CATEGORY_TYPE = [
    (r"Upright Vacuums|Canister Vacuums", "vacuum-upright/canister"),
    (r"Stick Vacuums", "vacuum-stick"),
    (r"Handheld Vacuums", "vacuum-handheld"),
    (r"Robotic Vacuums", "vacuum-robot"),
    (r"Steam Mops$|Steam Cleaners", "steam mop"),
    (r"Sweepers", "sweeper"),
    (r"Air Fryers|Deep Fryers", "air fryer"),
    (r"Countertop Blenders|Personal Size Blenders|^Blenders$", "blender"),
    (r"Food Processors$", "food processor"),
    (r"Coffee Machines|Coffee Makers|Espresso Machines|Drip Coffee", "coffee maker"),
    (r"Slow Cookers|Electric Pressure Cookers|Multicookers|Rice Cookers", "multicooker"),
    (r"Electric Grills|Indoor Grills|Contact Grills", "indoor grill"),
    (r"Toaster Ovens|Countertop Ovens|Convection Ovens", "countertop oven"),
    (r"Ice Cream Machines", "ice cream maker"),
    (r"Air Purifiers", "air purifier"),
    (r"^Irons$|Steamers", "iron/steamer"),
    (r"Cookware|Skillets|Pans|Knife|Cutlery|Bakeware", "cookware/cutlery"),
    (r"Hand Blenders", "blender"),
    (r"Choppers", "food processor"),
    (r"Mixers", "mixer"),
    (r"Parts|Accessories|Attachments|Filters|Brushes|Belts|Bags|Batteries|Replacement", "accessory/part"),
]
TITLE_TYPE = [
    (r"replacement|compatible|\bfor (shark|ninja)\b|part no|genuine shark|filter|brush ?roll|attachment|\bbelt\b|accessory|cups? with (sip )?lids|cleaning pad|disc blade|shelf", "accessory/part"),
    (r"air fry", "air fryer"),
    (r"robot", "vacuum-robot"),
    (r"stick vac|cordless stick|rocket|vertex|wandvac|\bhv\d", "vacuum-stick"),
    (r"handheld|\bhand vac", "vacuum-handheld"),
    (r"upright|navigator|rotator|lift-?away|canister", "vacuum-upright/canister"),
    (r"steam (pocket )?mop|steam cleaner", "steam mop"),
    (r"blender|nutri ninja|auto-?iq|kitchen system|blend", "blender"),
    (r"food processor|chop|master prep|food & drink maker", "food processor"),
    (r"cooking system|multi ?cooker", "multicooker"),
    (r"mixer", "mixer"),
    (r"coffee|espresso", "coffee maker"),
    (r"pressure cook|slow cook|foodi|possible ?cooker", "multicooker"),
    (r"grill", "indoor grill"),
    (r"oven|toaster", "countertop oven"),
    (r"creami|ice cream", "ice cream maker"),
    (r"purifier", "air purifier"),
    (r"\biron\b|steamer", "iron/steamer"),
    (r"cookware|skillet|\bpan\b|knife|knives", "cookware/cutlery"),
    (r"sweeper", "sweeper"),
    (r"juicer", "juicer"),
    (r"kettle", "kettle"),
    (r"waffle", "waffle maker"),
    (r"cleanser|cleaning solution", "floor-care consumable"),
    (r"steam", "steam mop"),
    (r"frother", "coffee maker"),
    (r"cookbook", "other"),
    (r"vacuum|\bvac\b|stickvac", "vacuum-other"),
]


# Accessory detection by word position. Strong words mark a part anywhere in the title; weak words only when
# they come before any main-unit noun ("Upright Vacuum with ... HEPA Filter" is a vacuum, "Filter for NV360" is a part).
ACC_STRONG = re.compile(r"(?i)replacement|compatible|\bfor (shark|ninja)\b|part no|\bgenuine\b|\bkit\b|\bfits\b|\brefills?\b|accessory (holder|bag|kit|set)|"
                        r"cups? with (sip )?lids|cleaning pad|disc blade|shelf")
ACC_WEAK_WORDS = (r"\bfilters?\b|\blids?\b|\bpints?\b|\bblades?\b|\bhose\b|nozzle|dust (cup|bin)|dirt bin|brush ?roll|"
                  r"\bbrush(es)?\b|reservoir|\btank\b|\bpads?\b|\bbelts?\b|motor base|power base|\bgasket|sealing ring|\bpitcher\b|\bwand\b|\bbowl\b|"
                  r"\battachment\b|\bholder\b|\bgrinder\b|\bsleeve\b")
ACC_WEAK = re.compile(ACC_WEAK_WORDS, re.I)
# Title ends on a part word followed by a code with a digit ("Hand Vac Filter 18355").
ACC_WEAK_END = re.compile(r"(?:" + ACC_WEAK_WORDS + r")[\s,\-#]*[A-Z0-9]*\d[A-Z0-9]*\s*$", re.I)
# Main-unit nouns, including SharkNinja product-line names (a line name near the start means a whole unit).
UNIT_NOUN = re.compile(r"(?i)vacuum|\bvac\b|blender|coffee (bar|maker|brewer)|air fryer|\bgrill|cooker|oven|steam (pocket )?mop|processor|"
                       r"kitchen system|purifier|\biron\b|sweeper|juicer|kettle|creami|ice cream maker|foodi|toaster|steamer|mixer|chop|"
                       r"navigator|rotator|rocket|lift-?away|duoclean|apex|vertex|wandvac|\bion\b|\biq\b|robot|vacmop|nutri (ninja|bowl)|auto-?iq")
PART_CODE = re.compile(r"\b(\d{3,4}[A-Z]{2,4}\d{3}[A-Z]?|X[A-Z]{2,4}\d{2,4}[A-Z]?)\b")


def is_accessory_title(title):
    t = title or ""
    if ACC_STRONG.search(t):
        return True
    w, u = ACC_WEAK.search(t), UNIT_NOUN.search(t)
    if not w:
        return False
    # Title ends on the part word followed by a code ("Hand Vac Filter 18355").
    if ACC_WEAK_END.search(t):
        return True
    # Part code (1190FC500B, XSB726N) next to a part word, or the part word comes before any unit noun.
    return bool(PART_CODE.search(t)) or not u or w.start() < u.start()


BUNDLE_RE = re.compile(r"(?i)(vacuums?|mop|blender|cooker|fryer|grill|steamer)\b[^+]*\+\s*\S")


def product_type(categories, title):
    if BUNDLE_RE.search(title or "") and "+" in (title or ""):
        return "bundle", "title '+' joins two products"
    last = (categories or [None])[-1] if categories else None
    t = (title or "").lower()
    if is_accessory_title(title) or (last and not UNIT_NOUN.search(t) and re.search(r"Parts|Accessories|Attachments|Filters|Replacement", last)):
        return "accessory/part", "title/category accessory rule"
    if last:
        for pat, typ in CATEGORY_TYPE:
            if typ != "accessory/part" and re.search(pat, last):
                return typ, "category"
    for pat, typ in TITLE_TYPE[1:]:
        if re.search(pat, t):
            return typ, "title"
    return "unclassified", "none"


# Unit core model: letters + digits identify the unit; what follows is colour / retailer / bundle variant
# (WS642BL = WS642GN, QB751QBK = QB751QCN, CS970QSS = CS970QFM). Checked against blind labels, see eval/.
CORE_RE = re.compile(r"^([A-Z]{1,4}\d{2,5})")


def core_model(base_model):
    if not base_model:
        return None
    m = CORE_RE.match(base_model)
    return m.group(1) if m else base_model


# ---------------- units ----------------
def capacity_qt(details_capacity, title):
    for raw, src in ((details_capacity, "details"), (title, "title")):
        if not raw:
            continue
        s = str(raw)
        pats = [(r"([\d.]+)\s*-?\s*(?:qt|quarts?)\b", 1.0), (r"([\d.]+)\s*-?\s*(?:liters?|l)\b", 1 / 0.946353),
                (r"([\d.]+)\s*-?\s*(?:fl\.? ?oz|fluid ounces?|oz|ounces?)\b", 1 / 32), (r"([\d.]+)\s*-?\s*cups?\b", 1 / 4),
                (r"([\d.]+)\s*-?\s*(?:ml|milliliters?)\b", 1 / 946.353)]
        for p, f in pats:
            m = re.search(p, s, re.I)
            if m:
                try:
                    return round(float(m.group(1)) * f, 2), src
                except ValueError:
                    pass
    return None, None


def wattage_w(details_wattage, title):
    for raw, src in ((details_wattage, "details"), (title, "title")):
        if not raw:
            continue
        m = re.search(r"(\d{2,4}(?:\.\d+)?)\s*-?\s*(?:watts?|w)\b", str(raw), re.I) or (
            re.fullmatch(r"\s*(\d{2,4})(?:\.0+)?\s*", str(raw)) if src == "details" else None)
        if m:
            return float(m.group(1)), src
    return None, None


# ---------------- maker ----------------
# Store names 'Shark' / 'Ninja' also catch unrelated brands (Shark Skinz, Sharkk, NINJA Brand rug pads,
# Teenage Mutant Ninja Turtles). Title evidence decides.
UNRELATED_RE = re.compile(r"(?i)shark ?skinz|sharkk|ninja brand|ninja rug pad|rug pad|gripper pad|teenage mutant|nickelodeon|buddha|tote bag|canvas bag|soap dispenser|dancing shark|soapstone")
SN_BRAND_RE = re.compile(r"(?i)\b(shark|ninja|nutri ninja|sharkninja|euro-?pro)\b")
# SharkNinja product-line names: brand proof when the title omits 'Shark'/'Ninja'.
SN_LINE_RE = re.compile(r"(?i)navigator|rotator|rocket|lift-?away|duoclean|mega kitchen system|professional plus kitchen system|"
                        r"foodi|express chop|auto-?iq|nutri|creami|vertex|ionflex|wandvac|\bbl\d{3}|\bsv\d{3,4}|steam pocket")
THIRD_PARTY_RE = re.compile(r"(?i)^(replacement|compatible|for |fits )|\bcompatible with\b|\breplacement for\b|\bfits\b")


def maker(title, is_accessory, store):
    """sharkninja | third_party_compatible | unrelated | unverified (store says Shark/Ninja, no evidence either way)."""
    t = title or ""
    if UNRELATED_RE.search(t):
        return "unrelated"
    if is_accessory and THIRD_PARTY_RE.search(t) and not re.search(r"(?i)genuine|original|oem", t):
        head = COMPAT_RE.split(t, maxsplit=1)[0]
        if not SN_BRAND_RE.search(head):
            return "third_party_compatible"
    if SN_BRAND_RE.search(t) or SN_LINE_RE.search(t):
        return "sharkninja"
    return "unverified"


RENEWED_RE = re.compile(r"(?i)\(renewed\)|\brenewed\b|refurbish|factory serviced")


# ---------------- generic text (benchmarks) ----------------
_PUNCT = str.maketrans("", "", string.punctuation)


def norm_text(v):
    return "" if is_missing(v) else re.sub(r"\s+", " ", str(v).lower().translate(_PUNCT)).strip()


BRAND_ALIASES = {"hewlett packard": "hp", "hewlettpackard": "hp", "hewlett-packard": "hp"}


def norm_brand(v):
    if is_missing(v):
        return None
    s = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", "", str(v).lower())).strip()
    return BRAND_ALIASES.get(s, s) or None


GENERIC_MODEL_RE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9\-/]{4,}$", re.I)
UNIT_RE = re.compile(r"^\d+(\.\d+)?(gb|tb|mb|mp|hz|ghz|mm|cm|in|inch|ft|oz|lb|lbs|w|v|hr|hrs|pack|ct|pc|pcs|x)$", re.I)


def generic_model_tokens(title):
    if is_missing(title):
        return []
    out = []
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/]*", str(title)):
        if UNIT_RE.match(tok) or not GENERIC_MODEL_RE.match(tok):
            continue
        n = re.sub(r"[\s\-_/]+", "", tok.lower())
        if len(n) >= 4:
            out.append(n)
    return list(dict.fromkeys(out))


def norm_modelno(v):
    if is_missing(v):
        return None
    s = re.sub(r"[\s\-_/.]+", "", str(v).lower())
    return s or None
