"""Complaint themes and stated time to failure, tagged with deterministic rules (no model involved).

Every review (all star ratings, both brands sets) gets one flag per theme and, when the owner says the product stopped
working and says when, a failure-time band. Themes describe what owners wrote; shares of them are shares of
self-selected complaints, never failure rates.
Precision per theme is measured on a blind-labelled sample (eval/theme_labels.csv, eval/theme_eval.py); themes that
read poorly are listed in WEAK_THEMES and kept out of the pages.

In:  data/clean/sn_review.parquet, data/clean/cmp_review.parquet (if present)
Out: data/clean/sn_review_theme.parquet, data/clean/cmp_review_theme.parquet
Run: .venv/bin/python pipeline/themes.py"""
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression")
ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"

# Product-problem themes. Order is display order within a group.
THEMES = {
    # it stopped
    "stopped_working": r"\b(stopped working|quit working|quit on me|died|no longer (works|turns on|runs|charges|heats)|won'?t (turn on|power on|start|charge)|will not (turn on|power on|start|charge)|doesn'?t turn on|does not turn on|stopped (turning on|charging|heating|running|brewing|blending))\b",
    "dead_on_arrival": r"\b(dead on arrival|doa)\b|(never|didn'?t|did not|wouldn'?t|would not) (even )?(work|turn on|power on|start)(ed)? (at all )?(right )?(out of the box|from (the )?(start|beginning|first day|day one))|arrived (dead|not working)|never worked( at all)?[.!]|out of the box.{0,30}(didn'?t|did not|wouldn'?t|would not|won'?t) (work|turn on|power on)",
    # hardware
    "battery_runtime": r"\b(battery (life|died|dies|won'?t|doesn'?t|only|lasts?|drain\w*|is (dead|shot|terrible|weak))|run ?time|(only|barely) (lasts?|runs?) (for )?(about )?\d+ min|\d+ minutes? (of )?(run|use|charge)|(doesn'?t|won'?t|will not|does not) (hold|keep) (a |its |the )?charge)",
    "suction_loss": r"\b(lost (its |all )?suction|los(es|ing) suction|no suction|(weak|poor|little|bad|zero) suction|suction (is|was|got|became) (weak|poor|bad|terrible|gone))\b",
    "brush_roll": r"\b(brush ?roll|brushroll|roller ?brush|beater bar|brush (stopped|quit|won'?t|doesn'?t|no longer) (spin|turn|rotat)|roller (stopped|quit|won'?t|doesn'?t))",
    "part_broke": r"\b(hose|wand|handle|latch|hinge|clip|wheel|nozzle|button|switch|trigger|knob|base|attachment) (broke|cracked|snapped|split|fell off|came off|tore|ripped|broke off)|(broke|cracked|snapped) (the |a |my )?(hose|wand|handle|latch|clip|wheel|button)\b",
    "leak": r"\b(leak|leaks|leaking|leaked|leakage)\b",
    "jar_lid_blade": r"\b(pitcher|jar|cup|lid|blade|blades|gasket|seal|carafe) (cracked|crack|broke|leaks?|leaking|rusted|fell apart|stripped|came loose|loose|melted)|(cracked|broken|broke the|loose|dull|rust(y|ed)) (pitcher|jar|cup|lid|blade|blades|gasket|carafe)\b",
    "motor_burn_smell": r"\b(motor (burn\w*|died|blew|smok\w*|quit)|burning smell|burnt smell|burned smell|smell(s|ed)? like (it'?s )?burn\w*|smoke (came|coming|started|pouring)|overheat(s|ed|ing)?)\b",
    "coating_peel": r"\b(coating|non-?stick|teflon|finish|paint|surface) .{0,25}(peel\w*|flak\w*|chip\w*|came off|coming off|wore off|wearing off)|(peel\w*|flak\w*|chipp\w*) .{0,15}(coating|non-?stick|teflon)",
    "error_code": r"\b(error (code|message|light)|flashing (red|lights?)|blinking (red|lights?)|e\d{1,2} (error|code))\b",
    # use
    "app_connectivity": r"\b(app (won'?t|doesn'?t|does not|keeps|kept|crash\w*|never|stopped|freez\w*|glitch\w*|is (useless|terrible|horrible|awful|buggy|glitchy|garbage))|(the|shark|ninja) app .{0,40}(won'?t|doesn'?t|can'?t|couldn'?t|not work|never|fail\w*|error)|wifi|wi-fi|bluetooth|(won'?t|can'?t|couldn'?t|would not|unable to|will not) (connect|pair|sync)|connectivity|(lose|loses|lost|losing|drops?) (the )?(connection|wifi|its map|the map|map)|(map|mapping) (fail\w*|never|doesn'?t|won'?t|keeps|disappear\w*|lost|reset\w*|is (terrible|wrong|useless)))",
    "navigation": r"\b(stuck (on|under) (the |a |my )?(rug|rugs|carpet|furniture|couch|bed|chair|cords?|edge|threshold)|can'?t find (its|the) (dock|base|home|charger)|(never|doesn'?t|won'?t|couldn'?t) (find|return to|go back to) (its|the) (dock|base|home|charger)|misses (spots|areas|rooms|half)|bumps into|goes in circles|(runs|drives|goes) around in circles)\b",
    "noise": r"\b(so loud|very loud|extremely loud|too loud|really loud|loud(er)? than|noisy|deafening|high[- ]pitched (noise|whine|sound))\b",
    "heavy_awkward": r"\b(too heavy|very heavy|so heavy|really heavy|heavy and|bulky|top heavy|tips over|falls over|awkward to (use|push|carry|maneuver))\b",
    "not_hot_cook": r"\b(doesn'?t get hot|does not get hot|not hot enough|never gets hot|doesn'?t (heat|stay hot|keep (it|coffee) hot)|lukewarm|takes (forever|too long) to (heat|cook|brew|warm)|undercooked|uneven(ly)? (cook\w*|heat\w*)|burn(s|t|ed) (the )?(food|everything|bottom))\b",
    "no_steam": r"\b(no steam|won'?t steam|doesn'?t steam|does not steam|stopped steaming|barely steams|not (enough|much) steam|little (to no )?steam)\b",
    "clog": r"\b(clog|clogs|clogged|clogging)\b",
    "hair_wrap": r"\b(hair (wraps?|wrapped|tangles?|tangled|gets? (wrapped|tangled|stuck))|tangled (hair|up))\b",
    "hard_to_clean": r"\b(hard to clean|difficult to clean|pain to clean|impossible to clean|nightmare to clean)\b",
    # arrival (delivery and fulfilment)
    "arrived_damaged_used": r"\b(arrived|came|showed up|received it) (broken|damaged|used|dirty|dented|scratched|cracked|with (hair|dirt|dust|scratches))|(was|is|been) (clearly |obviously )?used before|already registered|previously used|someone else'?s (hair|dirt)",
    "missing_parts": r"\b(missing (parts|pieces|the |a |an |its |attachments|accessories|charger|manual|filter|lid|cord|tank|cap)|(no|without) (charger|manual|instructions|attachments|accessories) (in|was|included|came))",
    "not_as_described": r"\b(not (the )?(as|what) (described|pictured|advertised|ordered|i ordered)|wrong (item|model|product|color|version)|not (really )?(new|refurbished)|isn'?t (new|refurbished))\b",
    # service (reported separately; not a product problem)
    "warranty_service": r"\b(customer (service|support) (was|is|were) (terrible|horrible|awful|useless|no help|unhelpful|rude|non-?existent|a joke|the worst)|(terrible|horrible|awful|poor|useless|worst|bad) customer (service|support)|(no|never) (response|responded|called back|heard back)|warranty (claim|replacement|won'?t|wouldn'?t|doesn'?t|did not|didn'?t|refused|denied|voided|expired|ran out|process|is a joke)|out of warranty|(pay|paying|charged?) (to|for) (ship|shipping|return)|refused to (replace|refund|honor))",
}
GROUPS = {
    "It stopped": ["stopped_working", "dead_on_arrival"],
    "Hardware": ["battery_runtime", "suction_loss", "brush_roll", "part_broke", "leak", "jar_lid_blade",
                 "motor_burn_smell", "coating_peel", "error_code"],
    "In use": ["app_connectivity", "navigation", "noise", "heavy_awkward", "not_hot_cook", "no_steam", "clog",
               "hair_wrap", "hard_to_clean"],
    "On arrival": ["arrived_damaged_used", "missing_parts", "not_as_described"],
    "Service": ["warranty_service"],
}
LABELS = {
    "stopped_working": "Stopped working", "dead_on_arrival": "Dead on arrival", "battery_runtime": "Battery and run time",
    "suction_loss": "Suction loss", "brush_roll": "Brush roll", "part_broke": "A part broke", "leak": "Leaks",
    "jar_lid_blade": "Jar, lid or blade", "motor_burn_smell": "Motor, burning smell", "coating_peel": "Coating peels",
    "error_code": "Error codes", "app_connectivity": "App and connection", "navigation": "Navigation",
    "noise": "Noise", "heavy_awkward": "Heavy or awkward", "not_hot_cook": "Heating problems",
    "no_steam": "No steam", "clog": "Clogs", "hair_wrap": "Hair wrap", "hard_to_clean": "Hard to clean",
    "arrived_damaged_used": "Arrived damaged or used", "missing_parts": "Missing parts",
    "not_as_described": "Not as described", "warranty_service": "Warranty and service",
}
# Themes whose measured precision (eval/theme_eval.py) is below 0.7 are tagged but never shown.
_PREC = ROOT / "eval/theme_precision.csv"
WEAK_THEMES = set(pd.read_csv(_PREC).query("precision < 0.7").theme) if _PREC.exists() else set()

# ---------------- stated time to failure ----------------
NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
       "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "couple": 2, "couple of": 2, "few": 3, "a few": 3}
TIME_RE = re.compile(
    r"\b(?:after|within|in|lasted(?: only| just| about| maybe)?|only|for|less than|under|just (?:over|under|shy of)|about|around|barely|nearly|almost)\s+"
    r"(?:(?:only|just|about|around|maybe|over|under)\s+)?"
    r"(\d{1,2}|a few|a couple of|a couple|couple of|few|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(day|week|month|year)s?\b", re.I)
BANDS = [(1, "Under a month"), (4, "1 to 3 months"), (12, "4 to 11 months"), (24, "About a year"), (999, "2 years or more")]
BAND_ORDER = [b for _, b in BANDS]


def months_of(n, unit):
    n = n.lower().replace("a couple of", "couple of").replace("a couple", "couple")
    v = int(n) if n.isdigit() else NUM.get(n, NUM.get(n.replace("a ", ""), 1))
    u = unit.lower()
    return v / 30.4 if u == "day" else v / 4.35 if u == "week" else v if u == "month" else v * 12


def fail_months(text):
    m = TIME_RE.search(text)
    return months_of(m.group(1), m.group(2)) if m else np.nan


def band(mo):
    if np.isnan(mo) or mo > 72:
        return None
    for hi, name in BANDS:
        if mo < hi:
            return name
    return None


def tag(df):
    """df: review_id, rating, text. Returns review_id + one bool column per theme + fail_months, fail_band."""
    txt = df["text"].fillna("").str.lower()
    out = pd.DataFrame({"review_id": df["review_id"].values})
    for k, rx in THEMES.items():
        out[k] = txt.str.contains(rx, regex=True).values
    stop = out["stopped_working"].values
    fm = np.full(len(df), np.nan)
    idx = np.flatnonzero(stop)
    fm[idx] = [fail_months(t) for t in txt.values[idx]]
    out["fail_months"] = fm
    out["fail_band"] = [band(v) for v in fm]
    return out


def run(src, dst):
    r = pd.read_parquet(C / src, columns=["review_id", "rating", "review_title", "review_text"])
    r["text"] = r["review_title"].fillna("") + ". " + r["review_text"].fillna("")
    t = tag(r)
    t.to_parquet(C / dst, index=False)
    low = r["rating"].values <= 2
    share = t.loc[low, list(THEMES)].mean().sort_values(ascending=False)
    print(f"{dst}: {len(t):,} reviews; low-star {low.sum():,}; any product theme among low-star "
          f"{t.loc[low, [k for k in THEMES if k != 'warranty_service']].any(axis=1).mean():.1%}; "
          f"with failure band {t.fail_band.notna().sum():,}")
    print("  top low-star themes:", ", ".join(f"{k} {v:.1%}" for k, v in share.head(8).items()))


if __name__ == "__main__":
    run("sn_review.parquet", "sn_review_theme.parquet")
    if (C / "cmp_review.parquet").exists():
        run("cmp_review.parquet", "cmp_review_theme.parquet")
