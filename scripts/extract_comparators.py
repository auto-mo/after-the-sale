"""Stream the McAuley Lab Amazon Reviews 2023 files and keep only comparator-brand listings and their reviews.
Nothing large is written: files are read over HTTP, decompressed on the fly and filtered line by line.
Brands are matched on the listing's `store` field (exact, case-insensitive), the same way the SharkNinja set was built.
Outputs: data/raw/amazon2023/meta_comparators.jsonl, reviews_comparators.jsonl
Run: .venv/bin/python scripts/extract_comparators.py"""
import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/raw/amazon2023"
BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
META = [f"{BASE}/meta_categories/meta_Home_and_Kitchen.jsonl.gz", f"{BASE}/meta_categories/meta_Appliances.jsonl.gz"]
REVIEWS = f"{BASE}/review_categories/Home_and_Kitchen.jsonl.gz"
STORES = {"bissell": "Bissell", "dyson": "Dyson", "irobot": "iRobot", "keurig": "Keurig",
          "instant pot": "Instant Pot", "instant": "Instant Pot"}


def lines(url):
    with urllib.request.urlopen(url, timeout=120) as resp, gzip.GzipFile(fileobj=resp) as gz:
        for raw in gz:
            yield raw


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


keep = {}
meta_out = OUT / "meta_comparators.jsonl"
if meta_out.exists() and "--refresh-meta" not in sys.argv:
    for l in meta_out.open():
        d = json.loads(l)
        keep[d["parent_asin"]] = d["comparator_brand"]
    log(f"meta reused: {len(keep):,} listings")
else:
    with meta_out.open("w") as f:
        for url in META:
            n = 0
            for raw in lines(url):
                n += 1
                if b'"store"' not in raw:
                    continue
                d = json.loads(raw)
                brand = STORES.get((d.get("store") or "").strip().lower())
                if brand and d["parent_asin"] not in keep:
                    d["comparator_brand"] = brand
                    keep[d["parent_asin"]] = brand
                    f.write(json.dumps(d) + "\n")
                if n % 500_000 == 0:
                    log(f"{url.rsplit('/', 1)[-1]}: {n:,} lines, {len(keep):,} kept")
    log(f"meta done: {len(keep):,} listings")

needles = {a.encode() for a in keep}
n = kept = 0
with (OUT / "reviews_comparators.jsonl").open("w") as f:
    for raw in lines(REVIEWS):
        n += 1
        i = raw.find(b'"parent_asin": "')
        if i >= 0:
            j = i + 16
            if raw[j:raw.index(b'"', j)] in needles:
                f.write(raw.decode())
                kept += 1
        if n % 2_000_000 == 0:
            log(f"reviews: {n:,} lines, {kept:,} kept")
log(f"reviews done: {n:,} lines, {kept:,} kept")
