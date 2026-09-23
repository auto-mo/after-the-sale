"""Build explore/data_snapshot.html: every dataset we hold, its columns, fill rates and sample rows."""
import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "explore" / "data_snapshot.html"


def esc(v, n=90):
    s = "" if v is None else str(v)
    s = s.replace("\n", " ")
    return html.escape(s[:n] + ("…" if len(s) > n else ""))


def is_blank(v):
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return str(v).strip().lower() in ("", "nan", "none", "null")


def profile(df):
    rows = []
    for c in df.columns:
        col = df[c]
        filled = (~col.map(is_blank)).sum()
        vals = [v for v in col if not is_blank(v)]
        try:
            distinct = pd.Series([json.dumps(v) if isinstance(v, (list, dict)) else v for v in vals]).nunique()
        except TypeError:
            distinct = "—"
        ex = []
        for v in vals:
            s = json.dumps(v)[:60] if isinstance(v, (list, dict)) else str(v)
            if s not in ex:
                ex.append(s)
            if len(ex) == 3:
                break
        kind = type(vals[0]).__name__ if vals else "empty"
        rows.append((c, kind, filled, len(df), distinct, ex))
    return rows


def table_profile(df, note=None):
    out = ['<div class="scroll"><table class="prof"><thead><tr><th>Column</th><th>Type</th>'
           '<th class="num">Filled</th><th class="num">Distinct</th><th>Example values</th></tr></thead><tbody>']
    for c, kind, filled, n, distinct, ex in profile(df):
        pct = 100 * filled / n if n else 0
        cls = "low" if pct < 50 else ""
        out.append(
            f'<tr><td class="mono">{esc(c)}</td><td class="muted">{kind}</td>'
            f'<td class="num {cls}"><span class="bar"><i style="width:{pct:.0f}%"></i></span>{pct:.0f}%</td>'
            f'<td class="num">{distinct if isinstance(distinct, str) else f"{distinct:,}"}</td>'
            f'<td>{"<br>".join(esc(e, 70) for e in ex)}</td></tr>'
        )
    out.append("</tbody></table></div>")
    if note:
        out.append(f'<p class="note">{note}</p>')
    return "".join(out)


def table_sample(df, n=5, cols=None):
    d = df[cols] if cols else df
    d = d.head(n)
    head = "".join(f"<th>{esc(c)}</th>" for c in d.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(json.dumps(v) if isinstance(v, (list, dict)) else v, 60)}</td>" for v in r) + "</tr>"
        for r in d.itertuples(index=False)
    )
    return f'<div class="scroll"><table class="sample"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def read_jsonl(p):
    with open(p) as f:
        return [json.loads(l) for l in f]


sections, summary = [], []


def add(key, title, what, retailers, era, license_, role, blocks):
    summary.append((key, title, retailers, era, license_, role))
    sections.append(f'<section id="{key}"><h2>{html.escape(title)}</h2><p class="what">{what}</p>{"".join(blocks)}</section>')


# ---------- Amazon 2023: SharkNinja listings ----------
meta = read_jsonl(RAW / "amazon2023" / "meta_sharkninja.jsonl")
m = pd.DataFrame(meta)
m["segment"] = m["store"].map(lambda s: "Renewed (refurbished)" if s == "Amazon Renewed" else "Brand store")
top_level = ["parent_asin", "title", "store", "main_category", "average_rating", "rating_number", "price",
             "categories", "features", "description", "details", "images", "videos", "bought_together"]
m_top = m[[c for c in top_level if c in m.columns]]
det = pd.DataFrame([d.get("details") or {} for d in meta])
det_fill = (~det.map(is_blank)).sum().sort_values(ascending=False)
det_keep = [k for k in det_fill.index if k][:25]
seg = m["segment"].value_counts()
priced = m.groupby("segment")["price"].apply(lambda s: (~s.map(is_blank)).sum())
cat3 = m["categories"].map(lambda c: " › ".join(c[1:3]) if isinstance(c, list) and len(c) > 1 else "(none)")
cat_counts = cat3[m["segment"] == "Brand store"].value_counts().head(10)

blocks = [
    f'<div class="kpis"><div><b>{len(m):,}</b><span>listings</span></div>'
    f'<div><b>{seg.get("Brand store", 0):,}</b><span>sold under the Shark or Ninja store</span></div>'
    f'<div><b>{seg.get("Renewed (refurbished)", 0):,}</b><span>Amazon Renewed listings of Shark/Ninja items</span></div>'
    f'<div><b>{priced.get("Brand store", 0):,}</b><span>brand-store listings with a price</span></div></div>',
    "<h3>Top-level fields</h3>", table_profile(m_top, "<code>details</code> is a nested dictionary; its keys are profiled below. "
                                                      "<code>categories</code>, <code>features</code>, <code>description</code>, <code>images</code> are lists."),
    "<h3>Keys inside <code>details</code> (top 25 by fill)</h3>", table_profile(det[det_keep]),
    "<h3>Brand-store listings by category</h3><div class='scroll'><table class='sample'><thead><tr><th>Category</th><th class='num'>Listings</th></tr></thead><tbody>"
    + "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v}</td></tr>" for k, v in cat_counts.items()) + "</tbody></table></div>",
    "<h3>Sample rows (most-reviewed brand-store items)</h3>",
    table_sample(m[m["segment"] == "Brand store"].sort_values("rating_number", ascending=False),
                 8, ["parent_asin", "title", "store", "price", "average_rating", "rating_number"]),
]
add("amz-meta", "Amazon 2023: SharkNinja listings",
    "Product metadata from the McAuley Lab Amazon Reviews 2023 dataset (UCSD), filtered from 3.8M Home & Kitchen and "
    "Appliances items to Shark and Ninja. Prices and ratings are as crawled in 2023; there is no crawl date per row.",
    "Amazon", "Crawled 2023", "No license stated (academic dataset; cite McAuley Lab)", "Amazon side of the SharkNinja analysis", blocks)

# ---------- Amazon 2023: SharkNinja reviews ----------
rev_path = RAW / "amazon2023" / "reviews_sharkninja.jsonl"
if rev_path.exists() and rev_path.stat().st_size > 0:
    r = pd.DataFrame(read_jsonl(rev_path))
    r["date"] = pd.to_datetime(r["timestamp"], unit="ms")
    per_year = r["date"].dt.year.value_counts().sort_index()
    maxy = per_year.max()
    bars = "".join(
        f'<div class="yr"><span>{y}</span><span class="bar wide"><i style="width:{100 * c / maxy:.0f}%"></i></span><span class="num">{c:,}</span></div>'
        for y, c in per_year.items()
    )
    blocks = [
        f'<div class="kpis"><div><b>{len(r):,}</b><span>reviews</span></div>'
        f'<div><b>{r["parent_asin"].nunique():,}</b><span>listings with at least one review</span></div>'
        f'<div><b>{r["date"].min():%b %Y}</b><span>earliest</span></div>'
        f'<div><b>{r["date"].max():%b %Y}</b><span>latest</span></div></div>',
        "<h3>Fields</h3>", table_profile(r.drop(columns=["date"])),
        "<h3>Reviews per year</h3>", f'<div class="years">{bars}</div>',
        "<h3>Sample rows</h3>",
        table_sample(r.assign(date=r["date"].dt.date), 5, ["parent_asin", "date", "rating", "verified_purchase", "helpful_vote", "title", "text"]),
    ]
    add("amz-rev", "Amazon 2023: SharkNinja reviews",
        "Every review in the Home & Kitchen review file whose product is one of the listings above. Timestamps make rating-over-time and review velocity possible.",
        "Amazon", "1990s–Sep 2023", "No license stated (academic dataset; cite McAuley Lab)", "Time dimension: rating trend, review velocity", blocks)
else:
    summary.append(("amz-rev", "Amazon 2023: SharkNinja reviews", "Amazon", "—", "—", "Still extracting"))

# ---------- Cross-retailer benchmarks ----------
B = RAW / "benchmarks"


def pair_bench(key, name, left, right, what, era):
    s = pd.read_parquet(B / name / "source_source.parquet")
    t = pd.read_parquet(B / name / "target_target.parquet")
    p = pd.concat([pd.read_parquet(B / name / f"pairs_{x}.parquet") for x in ("train", "valid", "test")])
    matches = (p["label"].astype(str) == "1").sum()
    blocks = [
        f'<div class="kpis"><div><b>{len(s):,}</b><span>{left} rows</span></div><div><b>{len(t):,}</b><span>{right} rows</span></div>'
        f'<div><b>{len(p):,}</b><span>hand-labelled pairs</span></div><div><b>{matches:,}</b><span>labelled as same product ({100 * matches / len(p):.1f}%)</span></div></div>',
        f"<h3>{left} table</h3>", table_profile(s), table_sample(s, 4),
        f"<h3>{right} table</h3>", table_profile(t), table_sample(t, 4),
        "<h3>Labelled pairs</h3>", table_profile(p),
    ]
    add(key, name, what, f"{left} + {right}", era, "No license stated (academic benchmark)", "Matcher training/eval with ground truth", blocks)


pair_bench("wa", "Walmart-Amazon", "Walmart", "Amazon",
           "Product listings from Walmart and Amazon (mostly electronics) with hand-labelled same/not-same pairs. The closest public parallel to the "
           "SharkNinja question: two retailers, brand, model number and price on both sides.", "c. 2014–2015")
pair_bench("ab", "Abt-Buy", "Abt", "Buy.com",
           "Two electronics retailers (Abt.com and Buy.com); name, description and price with labelled pairs.", "c. 2010")
pair_bench("ag", "Amazon-Google", "Amazon", "Google Products",
           "Software products listed on Amazon and Google Products with labelled pairs.", "c. 2010")

pr = pd.read_parquet(B / "product-matching" / "default_train.parquet")
cats = pr["Category Label"].value_counts()
blocks = [
    f'<div class="kpis"><div><b>{len(pr):,}</b><span>offers</span></div><div><b>{pr["Vendor ID"].nunique():,}</b><span>vendors (e-shops)</span></div>'
    f'<div><b>{pr["Cluster ID"].nunique():,}</b><span>distinct products (clusters)</span></div><div><b>{len(cats)}</b><span>categories</span></div></div>',
    "<h3>Fields</h3>", table_profile(pr),
    "<h3>Offers by category</h3><div class='scroll'><table class='sample'><thead><tr><th>Category</th><th class='num'>Offers</th></tr></thead><tbody>"
    + "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v:,}</td></tr>" for k, v in cats.items()) + "</tbody></table></div>",
    "<h3>Sample rows (one product across vendors)</h3>", table_sample(pr[pr["Cluster ID"] == pr["Cluster ID"].iloc[0]], 6),
]
add("pr", "PriceRunner multi-vendor offers",
    "Offers crawled from the PriceRunner comparison site (UK/EU; some titles are German): the same product listed by many shops, grouped into clusters. "
    "Includes home appliances (fridges, washing machines, dishwashers, microwaves). Titles only: no price, rating or brand column.",
    "306 vendors", "c. 2019–2020", "GPL-2.0", "Many-vendor matching; appliance titles", blocks)

oc = B / "ecommerce-retail-product-matching-workflow-dataset"
cw = pd.read_parquet(oc / "candidate_workflow_train.parquet")
blocks = [
    f'<div class="kpis"><div><b>{len(cw):,}</b><span>candidate match rows</span></div><div><b>{cw["source_product_id_masked"].nunique():,}</b><span>source products</span></div>'
    f'<div><b>{cw.shape[1]}</b><span>columns</span></div></div>',
    "<h3>Fields</h3>", table_profile(cw),
    "<h3>Sample rows</h3>", table_sample(cw, 4, ["normalized_product_type", "candidate_retailer_masked", "upc_signal", "model_number_signal",
                                                 "title_signal", "match_confidence_score", "confidence_band", "output_bucket", "decision_reason_category"]),
]
add("oc", "Octoparse product-matching workflow sample",
    "A vendor's sanitised preview of a commercial retail matching workflow, including small kitchen appliances. Titles, brands, UPCs and model numbers "
    "are masked, so it cannot be matched on. Useful only as a reference for how a production matcher structures signals, confidence bands and review routing.",
    "Masked", "2026 (synthetic preview)", "CC BY-NC 4.0", "Design reference only", blocks)

# ---------- Page ----------
summary_rows = "".join(
    f'<tr><td><a href="#{k}">{html.escape(t)}</a></td><td>{html.escape(rt)}</td><td>{html.escape(era)}</td><td>{html.escape(lic)}</td><td>{html.escape(role)}</td></tr>'
    for k, t, rt, era, lic, role in summary
)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Snapshot</title>
<style>
:root{{--bg:#F4F6FB;--surface:#fff;--ink:#16202E;--muted:#5B6678;--line:#DCE2EC;--accent:#1F6FE5;--warn:#B4541A;--bar:#D6E4FB}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0C1622;--surface:#122033;--ink:#ECF1F8;--muted:#9AA7BA;--line:#23344B;--accent:#5B9BFF;--warn:#F0A060;--bar:#1D3558}}}}
:root[data-theme="dark"]{{--bg:#0C1622;--surface:#122033;--ink:#ECF1F8;--muted:#9AA7BA;--line:#23344B;--accent:#5B9BFF;--warn:#F0A060;--bar:#1D3558}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:32px 16px 80px}}h1{{font-size:28px;margin:0 0 4px}}h2{{font-size:21px;margin:0 0 6px}}h3{{font-size:15px;margin:22px 0 8px}}
.lede{{color:var(--muted);max-width:760px}}section{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:22px;margin-top:22px}}
.what{{color:var(--muted);max-width:820px;margin:0 0 14px}}a{{color:var(--accent)}}code,.mono{{font-family:ui-monospace,Menlo,monospace;font-size:13px}}
.scroll{{overflow-x:auto;border:1px solid var(--line);border-radius:8px}}table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:var(--bg);font-weight:600;white-space:nowrap}}
tr:last-child td{{border-bottom:0}}.num{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}.muted{{color:var(--muted)}}.low{{color:var(--warn)}}
.bar{{display:inline-block;width:46px;height:6px;background:var(--bar);border-radius:3px;margin-right:6px;vertical-align:middle;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--accent)}}
.bar.wide{{width:100%;height:10px}}.years{{display:grid;gap:4px;max-width:560px}}.yr{{display:grid;grid-template-columns:48px 1fr 80px;gap:10px;align-items:center;font-size:13px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:8px 0 4px}}.kpis div{{border-left:3px solid var(--accent);padding:2px 12px}}
.kpis b{{display:block;font-size:22px;font-variant-numeric:tabular-nums}}.kpis span{{color:var(--muted);font-size:13px}}.note{{color:var(--muted);font-size:13px}}
.sample td{{max-width:340px}}
</style></head><body><main>
<h1>Data snapshot</h1>
<p class="lede">Everything collected so far, profiled column by column. Working assumption: treat 2023 as "now", because the Amazon data stops in September 2023. Eras marked "c." are approximate, inferred from when each benchmark was published. Filled = share of rows where the field is non-empty; orange marks fields under 50% filled.</p>
<section><h2>What we have</h2><div class="scroll"><table><thead><tr><th>Dataset</th><th>Retailers</th><th>Era</th><th>License</th><th>Role</th></tr></thead><tbody>{summary_rows}</tbody></table></div>
<p class="note">Not included: Kaggle datasets (need a Kaggle account and API token), WDC Products (large; electronics, shoes, watches), Home Depot search-relevance data (no price or rating).</p></section>
{"".join(sections)}
</main></body></html>"""
OUT.write_text(page)
print("wrote", OUT, f"{OUT.stat().st_size / 1024:.0f} KB")
