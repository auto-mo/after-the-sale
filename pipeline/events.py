"""Phase 6: event tests ("what moved what") with a comparison group, plus a placebo check.

Event types
  sibling_launch  another unit in the same family and product type launches (event month = its launch month)
  refurbished     refurbished units of the product start appearing (first refurbished review)
  low_rating      a month whose new-unit rating is >= 0.3 below the trailing 12-month average (>= 10 reviews that month)

Method (deterministic; all arithmetic here, never in a model)
  outcome   mean monthly NEW-unit reviews, pre window [m0-W, m0-1] vs post window [m0+1, m0+W], event month excluded,
            only months with data (from the product's first review month) and never past COMPLETE_THROUGH.
  change    d = ln((post + 0.5) / (pre + 0.5))
  controls  up to 10 unit products of the same product type, other families, with data covering both windows,
            pre volume within 3x, launched within 24 months, and no event of the same kind inside the window.
  effect    exp(d_product - mean(d_controls)) - 1
  range     5th-95th percentile over 1,000 resamples (controls with replacement; product counts Poisson)
  range     widened by the natural swing of products with no event, calibrated on placebo set A (fake dates)
  verdict   moved: |effect| >= 15% and range excludes 0 · no_clear_change: otherwise · not_enough_data: < 30 reviews
            in the pre window, < 3 comparison products, or too few months. False-alarm rate checked on placebo set B.
Outputs (data/clean/): sn_event_test, sn_event_band, sn_event_control, events_report.md
Run: .venv/bin/python pipeline/events.py"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
COMPLETE = pd.Period("2023-03", "M")
THRESH, MIN_PRE_REVIEWS, MIN_CONTROLS, MAX_CONTROLS, N_BOOT = 0.15, 30, 3, 10, 1000
WINDOWS = {"sibling_launch": 12, "refurbished": 12, "low_rating": 3}
rng = np.random.default_rng(20260923)

panel = pd.read_parquet(C / "sn_panel_month.parquet")
summ = pd.read_parquet(C / "sn_product_summary.parquet")
panel["m"] = pd.PeriodIndex(pd.to_datetime(panel["month"]), freq="M")

units = summ[(~summ.is_accessory) & (~summ.product_id.str.startswith("SN-B-")) & (summ.maker != "unrelated")].copy()
units["launch_m"] = pd.PeriodIndex(pd.to_datetime(units.launch_date), freq="M")
new = panel[panel.channel == "new"]
series = {pid: g.set_index("m")["reviews"] for pid, g in new.groupby("product_id")}
rating = {pid: g.set_index("m")[["reviews", "avg_rating"]] for pid, g in new.groupby("product_id")}
first_m = {pid: s.index.min() for pid, s in series.items()}
units = units[units.product_id.isin(series)]
info = units.set_index("product_id")


def window(pid, m0, W):
    """Return (pre_vals, post_vals) as arrays of monthly counts within valid data months, or None."""
    s = series.get(pid)
    if s is None:
        return None
    pre_m = [m0 - k for k in range(W, 0, -1) if m0 - k >= first_m[pid]]
    post_m = [m0 + k for k in range(1, W + 1) if m0 + k <= COMPLETE]
    need = max(2, W // 2)
    if len(pre_m) < need or len(post_m) < need:
        return None
    return s.reindex(pre_m, fill_value=0).to_numpy(), s.reindex(post_m, fill_value=0).to_numpy()


def dchange(pre_mean, post_mean):
    return np.log((post_mean + 0.5) / (pre_mean + 0.5))


# ---------------- events ----------------
events = []
fam_units = units.dropna(subset=["family"])
for fam, g in fam_units.groupby("family"):
    for p in g.itertuples():
        for s in g.itertuples():
            if s.product_id == p.product_id or s.product_type != p.product_type or pd.isna(s.launch_m):
                continue
            m0 = s.launch_m
            if first_m[p.product_id] <= m0 - 6 and m0 + 6 <= COMPLETE:
                events.append(dict(product_id=p.product_id, event_type="sibling_launch", event_month=m0,
                                   related_product=s.product_id, detail=f"{s.model_key or s.product_id} launched"))
for p in units.itertuples():
    if pd.notna(p.first_review_renewed):
        m0 = pd.Period(pd.to_datetime(p.first_review_renewed), "M")
        if first_m[p.product_id] <= m0 - 6 and m0 + 6 <= COMPLETE:
            events.append(dict(product_id=p.product_id, event_type="refurbished", event_month=m0, related_product=None,
                               detail="first refurbished review"))
for pid, r in rating.items():
    if pid not in info.index:
        continue
    r = r.sort_index()
    last = None
    for i in range(12, len(r)):
        m = r.index[i]
        if m > COMPLETE - 3:
            break
        row = r.iloc[i]
        trail = r.iloc[i - 12:i]
        n_tr = trail.reviews.sum()
        if row.reviews >= 10 and n_tr >= 30 and pd.notna(row.avg_rating):
            tavg = (trail.reviews * trail.avg_rating.fillna(0)).sum() / n_tr
            if row.avg_rating <= tavg - 0.3 and (last is None or (m - last).n >= 6):
                events.append(dict(product_id=pid, event_type="low_rating", event_month=m, related_product=None,
                                   detail=f"{row.avg_rating:.2f} vs trailing {tavg:.2f} ({int(row.reviews)} reviews)"))
                last = m
E = pd.DataFrame(events)
# Several siblings launching in the same month are one event for the product, not several identical tests.
sib = E[E.event_type == "sibling_launch"]
sib = (sib.groupby(["product_id", "event_month"], as_index=False)
          .agg(related_product=("related_product", lambda x: ",".join(sorted(x))),
               detail=("detail", lambda x: "; ".join(sorted(x)) if len(x) < 4 else f"{len(x)} siblings launched")))
sib["event_type"] = "sibling_launch"
E = pd.concat([sib, E[E.event_type != "sibling_launch"]], ignore_index=True)

# event months per product and type, used to exclude contaminated controls
fam_launch = {fam: sorted(g.launch_m.dropna()) for fam, g in fam_units.groupby(["family", "product_type"])}
refurb_m = {p.product_id: pd.Period(pd.to_datetime(p.first_review_renewed), "M") for p in units.itertuples() if pd.notna(p.first_review_renewed)}
lowr = E[E.event_type == "low_rating"].groupby("product_id").event_month.apply(list).to_dict()


def contaminated(cid, etype, m0, W):
    c = info.loc[cid]
    if etype == "sibling_launch":
        if pd.isna(c.family):
            return False
        return any(abs((lm - m0).n) <= W for lm in fam_launch.get((c.family, c.product_type), []) if lm != c.launch_m)
    if etype == "refurbished":
        return cid in refurb_m and abs((refurb_m[cid] - m0).n) <= W
    return any(abs((lm - m0).n) <= W for lm in lowr.get(cid, []))


by_type = {t: g.product_id.tolist() for t, g in units.groupby("product_type")}
BROAD = {"air fryer": "countertop cooking", "multicooker": "countertop cooking", "countertop oven": "countertop cooking",
         "indoor grill": "countertop cooking", "waffle maker": "countertop cooking",
         "blender": "food prep", "food processor": "food prep", "juicer": "food prep", "mixer": "food prep",
         "coffee maker": "beverage", "kettle": "beverage",
         "vacuum-upright/canister": "floor care", "vacuum-stick": "floor care", "vacuum-handheld": "floor care",
         "vacuum-robot": "floor care", "vacuum-other": "floor care", "steam mop": "floor care", "sweeper": "floor care"}
by_broad = {}
for t, ids in by_type.items():
    by_broad.setdefault(BROAD.get(t, t), []).extend(ids)
SIGMA, CALIBRATING = {}, False


def vol_band(pre_mean):
    return 0 if pre_mean < 5 else 1 if pre_mean < 20 else 2 if pre_mean < 50 else 3


def test_event(ev, eid):
    pid, etype, m0 = ev["product_id"], ev["event_type"], ev["event_month"]
    W = WINDOWS[etype]
    wp = window(pid, m0, W)
    base = dict(event_id=eid, **ev, window=W)
    if wp is None:
        return dict(base, verdict="not_enough_data", reason="not enough months of data around the event"), [], []
    pre, post = wp
    pm, qm = pre.mean(), post.mean()
    p = info.loc[pid]

    def pick(max_age, max_ratio, broad=False):
        cands = []
        pool = by_broad.get(BROAD.get(p.product_type, p.product_type), []) if broad else by_type.get(p.product_type, [])
        for cid in pool:
            if cid == pid or (pd.notna(p.family) and info.loc[cid].family == p.family):
                continue
            if pd.notna(p.launch_m) and pd.notna(info.loc[cid].launch_m) and abs((info.loc[cid].launch_m - p.launch_m).n) > max_age:
                continue
            # Life stage: months since first review at the event, within max(12, 50%) of the product's own.
            age_p, age_c = (m0 - first_m[pid]).n, (m0 - first_m[cid]).n
            if abs(age_c - age_p) > max(12, 0.5 * age_p):
                continue
            wc = window(cid, m0, W)
            if wc is None:
                continue
            cpre, cpost = wc
            if cpre.mean() <= 0 or not (1 / max_ratio <= (cpre.mean() + 0.5) / (pm + 0.5) <= max_ratio):
                continue
            if contaminated(cid, etype, m0, W):
                continue
            cands.append((abs(np.log((cpre.mean() + 0.5) / (pm + 0.5))), cid, cpre, cpost))
        cands.sort(key=lambda x: x[0])
        return cands[:MAX_CONTROLS]

    # Strict comparison first; a looser tier only when the strict one finds too few products (flagged).
    ctrl, tier = pick(24, 3), "strict"
    if len(ctrl) < MIN_CONTROLS:
        ctrl, tier = pick(48, 5), "relaxed"
    if len(ctrl) < MIN_CONTROLS:
        ctrl, tier = pick(48, 5, broad=True), "broad category"
    out = dict(base, pre_mean=round(pm, 2), post_mean=round(qm, 2), pre_reviews=int(pre.sum()), n_controls=len(ctrl), control_tier=tier)
    ctrl_rows = [dict(event_id=eid, control_product_id=cid, pre_mean=round(a.mean(), 2), post_mean=round(b.mean(), 2)) for _, cid, a, b in ctrl]
    if pre.sum() < MIN_PRE_REVIEWS:
        return dict(out, verdict="not_enough_data", reason=f"fewer than {MIN_PRE_REVIEWS} reviews before the event"), ctrl_rows, []
    if len(ctrl) < MIN_CONTROLS:
        return dict(out, verdict="not_enough_data", reason="fewer than 3 comparable products"), ctrl_rows, []
    dc = np.array([dchange(a.mean(), b.mean()) for _, _, a, b in ctrl])
    eff = float(np.exp(dchange(pm, qm) - dc.mean()) - 1)
    dcb = dc[rng.integers(0, len(dc), (N_BOOT, len(dc)))].mean(axis=1)
    pb = rng.poisson(pre.sum(), N_BOOT) / len(pre)
    qb = rng.poisson(post.sum(), N_BOOT) / len(post)
    log_eff = dchange(pm, qm) - dc.mean()
    boot_sd = float(np.std(dchange(pb, qb) - dcb))
    # Natural swing: products' before/after changes vary even with no event (life cycle, noise). Calibrated on
    # placebo set A by window length (5th-95th percentile spread); added to the resampling noise.
    sig = SIGMA.get(W, 0.0)
    sd = float(np.sqrt(boot_sd ** 2 + sig ** 2))
    lo, hi = np.exp(log_eff - 1.645 * sd) - 1, np.exp(log_eff + 1.645 * sd) - 1
    eff = float(np.exp(log_eff) - 1)
    if not CALIBRATING:
        if abs(eff) >= THRESH and (lo > 0 or hi < 0):
            verdict, reason = "moved", "change of at least 15% vs comparison, range excludes zero"
        else:
            # A "did not move" call would need the whole range inside +-15%; natural swings make that impossible
            # with review data, so the honest label is "no clear change".
            verdict, reason = "no_clear_change", "change is within the product's normal swings"
    else:
        verdict, reason = "calibration", ""
    out["log_effect"] = float(log_eff)
    # A fall to near zero usually means the product was being phased out; reviews alone cannot say why.
    out["near_zero_after"] = bool(qm < 0.2 * pm and qm < 1)
    if verdict == "moved" and out["near_zero_after"]:
        reason = "fell to near zero after the event; may be a planned discontinuation rather than an effect"
    # comparison band: controls scaled to the product's pre level, per relative month
    rel = list(range(-W, W + 1))
    s = series[pid]
    band = []
    for r in rel:
        m = m0 + r
        if m > COMPLETE:
            continue
        vals = []
        for _, cid, a, _ in ctrl:
            cs = series[cid]
            if m >= first_m[cid]:
                vals.append(cs.get(m, 0) * (pm + 0.5) / (a.mean() + 0.5))
        pv = s.get(m, 0) if m >= first_m[pid] else None
        if vals:
            band.append(dict(event_id=eid, rel_month=r, month=str(m), product_value=pv,
                             band_lo=float(np.percentile(vals, 25)), band_mid=float(np.median(vals)), band_hi=float(np.percentile(vals, 75))))
    return dict(out, effect_pct=round(100 * eff, 1), lo_pct=round(100 * lo, 1), hi_pct=round(100 * hi, 1), verdict=verdict, reason=reason), ctrl_rows, band


cand_units = [p for p in units.product_id if series[p].sum() >= 60]


def placebo_draws(n, etype_windows, tag):
    """Fake event months on products with no real event of that kind nearby."""
    out = []
    for k in range(n):
        pid = cand_units[rng.integers(0, len(cand_units))]
        et = ("sibling_launch", "low_rating")[k % 2]
        W = WINDOWS[et]
        lo_m, hi_m = first_m[pid] + W, COMPLETE - W
        if lo_m > hi_m:
            continue
        m0 = lo_m + int(rng.integers(0, (hi_m - lo_m).n + 1))
        if contaminated(pid, "sibling_launch", m0, 12) or contaminated(pid, "low_rating", m0, 3) or (pid in refurb_m and abs((refurb_m[pid] - m0).n) <= 12):
            continue
        r, _, _ = test_event(dict(product_id=pid, event_type=et, event_month=m0, related_product=None, detail="placebo"), f"{tag}{k}")
        out.append(r)
    return pd.DataFrame(out)


# 1) calibration on placebo set A: natural swing by (window, volume band), robust sd of log effects
CALIBRATING = True
A = placebo_draws(12000, WINDOWS, "A")
A = A.dropna(subset=["log_effect"])
# One swing per window length: the 5th-95th percentile spread of placebo log changes, so heavy tails count.
for w, g in A.groupby("window"):
    q05, q95 = np.percentile(g.log_effect, [5, 95])
    SIGMA[int(w)] = float((q95 - q05) / (2 * 1.645))
CALIBRATING = False

# 2) real events
rows, ctrls, bands = [], [], []
for i, ev in enumerate(E.to_dict("records")):
    r, c, b = test_event(ev, f"E{i:05d}")
    rows.append(r)
    ctrls += c
    bands += b
T = pd.DataFrame(rows)
T["event_month"] = T.event_month.astype(str)
T.to_parquet(C / "sn_event_test.parquet", index=False)
pd.DataFrame(bands).to_parquet(C / "sn_event_band.parquet", index=False)
pd.DataFrame(ctrls).to_parquet(C / "sn_event_control.parquet", index=False)

# 3) held-out placebo set B: false-alarm rate
B = placebo_draws(12000, WINDOWS, "B")
Bt = int((B.verdict != "not_enough_data").sum())
fa = (B.verdict == "moved").sum()
# ---------------- empirical p-values, false-discovery control, pooled averages ----------------
# Null = log effects on placebo set A (fake dates) with the same window. p = share of placebo |effects| >= this |effect|.
null = {int(w): np.sort(np.abs(g.log_effect.to_numpy())) for w, g in A.groupby("window")}


def emp_p(row):
    if pd.isna(row.get("log_effect")) or row["verdict"] == "not_enough_data":
        return np.nan
    n = null[int(row["window"])]
    return (np.sum(n >= abs(row["log_effect"])) + 1) / (len(n) + 1)


T["p_value"] = T.apply(emp_p, axis=1)
tested_mask = T.p_value.notna()
pv_sorted = T.loc[tested_mask, "p_value"].sort_values()
m = len(pv_sorted)
# Benjamini-Hochberg at q = 0.10
bh = pv_sorted.to_numpy() <= (np.arange(1, m + 1) / m) * 0.10
cut = pv_sorted.to_numpy()[np.nonzero(bh)[0].max()] if bh.any() else -1
T["survives_fdr"] = tested_mask & (T.p_value <= cut)
T.loc[(T.verdict == "moved") & ~T.survives_fdr, "reason"] = "change looked large, but not beyond what chance produces across this many tests"
T.loc[(T.verdict == "moved") & ~T.survives_fdr, "verdict"] = "no_clear_change"
T.to_parquet(C / "sn_event_test.parquet", index=False)

# Pooled average effect per event type (and direction of the average), bootstrap over events, vs placebo mean.
pooled = []
for et, g in T[tested_mask].groupby("event_type"):
    x = g.log_effect.to_numpy()
    w = int(g.window.iloc[0])
    base = A[A.window == w].log_effect.to_numpy()
    # Cluster bootstrap: resample products (a product can have several events), then all of its events.
    groups = [gg.log_effect.to_numpy() for _, gg in g.groupby("product_id")]
    diffs = []
    for _ in range(2000):
        pick_g = [groups[i] for i in rng.integers(0, len(groups), len(groups))]
        diffs.append(np.concatenate(pick_g).mean() - rng.choice(base, len(base)).mean())
    mean = x.mean() - base.mean()
    lo, hi = np.percentile(diffs, [5, 95])
    pooled.append(dict(event_type=et, n_events=len(x), n_products=g.product_id.nunique(), window=w,
                       avg_effect_pct=round(100 * (np.exp(mean) - 1), 1), lo_pct=round(100 * (np.exp(lo) - 1), 1),
                       hi_pct=round(100 * (np.exp(hi) - 1), 1),
                       verdict="moved" if (lo > 0 or hi < 0) else "no_clear_change"))
PO = pd.DataFrame(pooled)
PO.to_parquet(C / "sn_event_pooled.parquet", index=False)

lines = [f"events tested: {len(T):,}"]
for et, g in T.groupby("event_type"):
    vc = g.verdict.value_counts()
    lines.append(f"{et}: {len(g):,} events on {g.product_id.nunique():,} products; " + ", ".join(f"{k} {v:,}" for k, v in vc.items()))
mv = T[T.verdict == "moved"]
if len(mv):
    lines.append("moved direction: " + ", ".join(f"{et} up {int((g.effect_pct > 0).sum())} / down {int((g.effect_pct < 0).sum())}" for et, g in mv.groupby("event_type")))
lines.append("control tier (tested events): " + ", ".join(f"{k} {v:,}" for k, v in T.dropna(subset=["effect_pct"]).control_tier.value_counts().items())
             + " · moved by tier: " + ", ".join(f"{k} {v}" for k, v in T[T.verdict == "moved"].control_tier.value_counts().items()))
lines.append("not-enough-data reasons: " + ", ".join(f"{k} {v:,}" for k, v in T[T.verdict == "not_enough_data"].reason.value_counts().items()))
tested = int((T.verdict != "not_enough_data").sum())
lines.append(f"expected false 'moved' among real tested events at the placebo rate: about {fa / max(1, Bt) * tested:.0f} of {tested}; observed {int((T.verdict == 'moved').sum())}")
lines.append("calibrated natural swing (sd-equivalent of log change) by window: " + ", ".join(f"{k}: {v:.2f}" for k, v in sorted(SIGMA.items())))
lines.append(f"held-out placebo B: {len(B)} fake events; reached a verdict test {Bt}; false 'moved' {fa} "
             f"({100 * fa / max(1, Bt):.1f}% of those tested); by window: "
             + ", ".join(f"W={w} {int((g.verdict == 'moved').sum())}/{int((g.verdict != 'not_enough_data').sum())}" for w, g in B.groupby("window"))
             + f"; of the false 'moved', near-zero-after {int(((B.verdict == 'moved') & B.near_zero_after.fillna(False)).sum())}")
lines.append(f"calibration sample A tested: {len(A)} (by window: " + ", ".join(f"W={w} {len(g)}" for w, g in A.groupby('window')) + ")")
lines.append(f"real 'moved' flagged near-zero-after (possible discontinuation): {int(((T.verdict == 'moved') & T.near_zero_after.fillna(False)).sum())}")
lines.append(f"false-discovery control (BH q=0.10): {int(T.survives_fdr.sum())} of {m} tested events survive; final verdicts: "
             + ", ".join(f"{k} {v:,}" for k, v in T.verdict.value_counts().items()))
for r in PO.itertuples():
    lines.append(f"pooled {r.event_type}: {r.n_events} events on {r.n_products} products, average change {r.avg_effect_pct:+.1f}% "
                 f"[{r.lo_pct:+.1f}, {r.hi_pct:+.1f}] vs placebo → {r.verdict}")
print("\n".join(lines))
(C / "events_report.md").write_text("# Event tests report (pipeline/events.py)\n\n" + "\n".join(f"- {l}" for l in lines) + "\n")
