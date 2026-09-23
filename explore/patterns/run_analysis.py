import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import json
import duckdb
import pandas as pd
import numpy as np
from benchmarks_rules import (
    is_missing, parse_price, normalize_modelno, normalize_text, tokenize, jaccard,
    extract_model_tokens, modelno_in_title, normalize_brand, relative_price_diff,
)

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
BM = f"{ROOT}/data/raw/benchmarks"
con = duckdb.connect()

def load(path):
    return con.execute(f"select * from '{path}'").df()

results = {}

# ---------- Item 1: missing values + price formats ----------
def missing_price_report(name, side_path, cols):
    df = load(side_path)
    rep = {"name": name, "n_rows": len(df), "cols": {}}
    for c in cols:
        vals = df[c].astype(str)
        n_missing_nan_str = (vals.str.strip().str.lower() == "nan").sum()
        n_empty = (vals.str.strip() == "").sum()
        n_none = (vals.str.strip().str.lower() == "none").sum()
        n_ws_only = vals.apply(lambda x: x != "" and x.strip() == "").sum()
        rep["cols"][c] = {
            "n_missing_literal_nan": int(n_missing_nan_str),
            "n_empty_string": int(n_empty),
            "n_literal_none": int(n_none),
        }
    if "price" in df.columns:
        raw = df["price"]
        n_missing = raw.astype(str).str.strip().str.lower().isin(["nan", "", "none"]).sum()
        sample_nonmissing = raw[~raw.astype(str).str.strip().str.lower().isin(["nan", "", "none"])].astype(str).unique()[:15]
        parsed = raw.apply(parse_price)
        n_parsed = parsed.notna().sum()
        n_present = len(df) - n_missing
        rep["price"] = {
            "n_missing": int(n_missing),
            "n_present": int(n_present),
            "n_parsed_of_present": int(n_parsed),
            "parse_rate_of_present": round(n_parsed / n_present, 4) if n_present else None,
            "sample_raw_formats": list(sample_nonmissing),
        }
    return rep

item1 = []
item1.append(missing_price_report("Walmart-Amazon/source(Walmart)", f"{BM}/Walmart-Amazon/source_source.parquet", ["title","category","brand","modelno","price"]))
item1.append(missing_price_report("Walmart-Amazon/target(Amazon)", f"{BM}/Walmart-Amazon/target_target.parquet", ["title","category","brand","modelno","price"]))
item1.append(missing_price_report("Abt-Buy/source(Abt)", f"{BM}/Abt-Buy/source_source.parquet", ["name","description","price"]))
item1.append(missing_price_report("Abt-Buy/target(Buy)", f"{BM}/Abt-Buy/target_target.parquet", ["name","description","price"]))
item1.append(missing_price_report("Amazon-Google/source(Amazon)", f"{BM}/Amazon-Google/source_source.parquet", ["title","manufacturer","price"]))
item1.append(missing_price_report("Amazon-Google/target(Google)", f"{BM}/Amazon-Google/target_target.parquet", ["title","manufacturer","price"]))
results["item1"] = item1

# ---------- Item 2: model numbers ----------
def wa_model_analysis(split_path, s_df, t_df):
    pairs = load(split_path)
    s_idx = s_df.set_index("id")
    t_idx = t_df.set_index("id")
    rows = []
    for _, r in pairs.iterrows():
        lid, rid, label = r["ltable_id"], r["rtable_id"], r["label"]
        srow = s_idx.loc[lid]
        trow = t_idx.loc[rid]
        s_model = normalize_modelno(srow["modelno"])
        t_model = normalize_modelno(trow["modelno"])
        s_title_models = extract_model_tokens(srow["title"])
        t_title_models = extract_model_tokens(trow["title"])
        both_present = s_model is not None and t_model is not None
        either_missing = s_model is None or t_model is None
        exact_equal = both_present and s_model == t_model
        cross_in_title = False
        if s_model and s_model in t_title_models:
            cross_in_title = True
        if t_model and t_model in s_title_models:
            cross_in_title = True
        rows.append({
            "label": label, "lid": lid, "rid": rid,
            "s_model": s_model, "t_model": t_model,
            "either_missing": either_missing, "exact_equal": exact_equal,
            "cross_in_title": cross_in_title,
        })
    return pd.DataFrame(rows)

wa_s = load(f"{BM}/Walmart-Amazon/source_source.parquet")
wa_t = load(f"{BM}/Walmart-Amazon/target_target.parquet")
wa_all_pairs = pd.concat([
    load(f"{BM}/Walmart-Amazon/pairs_train.parquet"),
    load(f"{BM}/Walmart-Amazon/pairs_valid.parquet"),
    load(f"{BM}/Walmart-Amazon/pairs_test.parquet"),
])
wa_all_pairs.to_parquet("/tmp/_wa_allpairs.parquet")
wa_model_df = wa_model_analysis("/tmp/_wa_allpairs.parquet", wa_s, wa_t)

def summarize_model(df, label_val):
    sub = df[df["label"] == label_val]
    n = len(sub)
    return {
        "n": n,
        "pct_either_missing": round(sub["either_missing"].mean()*100, 2),
        "pct_exact_equal_of_all": round(sub["exact_equal"].mean()*100, 2),
        "pct_exact_equal_of_both_present": round(sub[~sub["either_missing"]]["exact_equal"].mean()*100, 2) if (~sub["either_missing"]).sum() else None,
        "pct_cross_in_title": round(sub["cross_in_title"].mean()*100, 2),
    }

item2 = {
    "walmart_amazon": {
        "matched": summarize_model(wa_model_df, "1"),
        "nonmatched": summarize_model(wa_model_df, "0"),
    }
}

# Model tokens extracted from titles for Abt-Buy and Amazon-Google (no modelno column)
def title_model_token_analysis(name, s_col, t_col, s_path, t_path, train_p, valid_p, test_p):
    s_df = load(s_path); t_df = load(t_path)
    s_idx = s_df.set_index("id"); t_idx = t_df.set_index("id")
    pairs = pd.concat([load(train_p), load(valid_p), load(test_p)])
    rows = []
    for _, r in pairs.iterrows():
        lid, rid, label = r["ltable_id"], r["rtable_id"], r["label"]
        s_text = s_idx.loc[lid][s_col]
        t_text = t_idx.loc[rid][t_col]
        s_tok = extract_model_tokens(s_text)
        t_tok = extract_model_tokens(t_text)
        either_missing = (len(s_tok) == 0) or (len(t_tok) == 0)
        overlap = len(s_tok & t_tok) > 0
        rows.append({"label": label, "either_missing": either_missing, "overlap": overlap})
    df = pd.DataFrame(rows)
    out = {}
    for lv in ["1", "0"]:
        sub = df[df["label"] == lv]
        out["matched" if lv == "1" else "nonmatched"] = {
            "n": len(sub),
            "pct_either_missing_tokens": round(sub["either_missing"].mean()*100, 2),
            "pct_token_overlap": round(sub["overlap"].mean()*100, 2),
        }
    return out

item2["abt_buy"] = title_model_token_analysis(
    "Abt-Buy", "name", "name",
    f"{BM}/Abt-Buy/source_source.parquet", f"{BM}/Abt-Buy/target_target.parquet",
    f"{BM}/Abt-Buy/pairs_train.parquet", f"{BM}/Abt-Buy/pairs_valid.parquet", f"{BM}/Abt-Buy/pairs_test.parquet",
)
item2["amazon_google"] = title_model_token_analysis(
    "Amazon-Google", "title", "title",
    f"{BM}/Amazon-Google/source_source.parquet", f"{BM}/Amazon-Google/target_target.parquet",
    f"{BM}/Amazon-Google/pairs_train.parquet", f"{BM}/Amazon-Google/pairs_valid.parquet", f"{BM}/Amazon-Google/pairs_test.parquet",
)
results["item2"] = item2

# ---------- Item 3: brand ----------
def brand_analysis():
    s_df = wa_s.set_index("id"); t_df = wa_t.set_index("id")
    pairs = wa_all_pairs
    rows = []
    for _, r in pairs.iterrows():
        srow = s_df.loc[r["ltable_id"]]; trow = t_df.loc[r["rtable_id"]]
        sb = normalize_brand(srow["brand"]); tb = normalize_brand(trow["brand"])
        rows.append({"label": r["label"], "sb": sb, "tb": tb,
                     "both_present": sb is not None and tb is not None,
                     "equal": (sb is not None and tb is not None and sb == tb)})
    df = pd.DataFrame(rows)
    out = {}
    for lv in ["1", "0"]:
        sub = df[df["label"] == lv]
        out["matched" if lv=="1" else "nonmatched"] = {
            "n": len(sub),
            "pct_both_present": round(sub["both_present"].mean()*100,2),
            "pct_brand_equal_of_both_present": round(sub[sub["both_present"]]["equal"].mean()*100,2) if sub["both_present"].sum() else None,
            "pct_brand_equal_of_all": round(sub["equal"].mean()*100,2),
        }
    # sample of brand values needing normalization (case only in this dataset; check aliasing needed)
    uniq_brands = pd.concat([s_df["brand"], t_df["brand"]]).dropna().unique()
    out["n_unique_brand_strings"] = int(len(uniq_brands))
    out["sample_brands"] = list(pd.Series(uniq_brands).sample(min(20,len(uniq_brands)), random_state=1))
    return out

results["item3"] = {"walmart_amazon": brand_analysis()}

# ---------- Item 4: title similarity + threshold tuning ----------
def title_sim_analysis(name, s_col, t_col, s_path, t_path, train_p, valid_p, test_p):
    s_df = load(s_path).set_index("id"); t_df = load(t_path).set_index("id")
    def build(pairs_path):
        pairs = load(pairs_path)
        sims, labels = [], []
        for _, r in pairs.iterrows():
            s_text = s_df.loc[r["ltable_id"]][s_col]
            t_text = t_df.loc[r["rtable_id"]][t_col]
            j = jaccard(tokenize(s_text), tokenize(t_text))
            sims.append(j); labels.append(int(r["label"]))
        return np.array(sims), np.array(labels)

    train_sims, train_labels = build(train_p)
    valid_sims, valid_labels = build(valid_p)
    test_sims, test_labels = build(test_p)

    tv_sims = np.concatenate([train_sims, valid_sims])
    tv_labels = np.concatenate([train_labels, valid_labels])

    def quantiles(sims, labels, lv):
        sub = sims[labels == lv]
        if len(sub) == 0:
            return None
        qs = [0, 10, 25, 50, 75, 90, 100]
        return {f"p{q}": round(float(np.percentile(sub, q)), 4) for q in qs}

    dist = {
        "matched_quantiles_all_splits": quantiles(np.concatenate([train_sims,valid_sims,test_sims]), np.concatenate([train_labels,valid_labels,test_labels]), 1),
        "nonmatched_quantiles_all_splits": quantiles(np.concatenate([train_sims,valid_sims,test_sims]), np.concatenate([train_labels,valid_labels,test_labels]), 0),
    }

    # tune threshold on train+valid: sweep, maximize F1
    best_t, best_f1 = None, -1
    for t in np.arange(0.01, 1.0, 0.01):
        pred = (tv_sims >= t).astype(int)
        tp = ((pred==1)&(tv_labels==1)).sum()
        fp = ((pred==1)&(tv_labels==0)).sum()
        fn = ((pred==0)&(tv_labels==1)).sum()
        prec = tp/(tp+fp) if (tp+fp)>0 else 0
        rec = tp/(tp+fn) if (tp+fn)>0 else 0
        f1 = 2*prec*rec/(prec+rec) if (prec+rec)>0 else 0
        if f1 > best_f1:
            best_f1, best_t = f1, t

    # evaluate on test
    pred_test = (test_sims >= best_t).astype(int)
    tp = ((pred_test==1)&(test_labels==1)).sum()
    fp = ((pred_test==1)&(test_labels==0)).sum()
    fn = ((pred_test==0)&(test_labels==1)).sum()
    prec = tp/(tp+fp) if (tp+fp)>0 else None
    rec = tp/(tp+fn) if (tp+fn)>0 else None
    f1 = 2*prec*rec/(prec+rec) if prec and rec and (prec+rec)>0 else None

    return {
        "distributions": dist,
        "tuned_threshold_on_train_valid": round(float(best_t), 3),
        "train_valid_f1_at_threshold": round(float(best_f1), 4),
        "test_precision": round(float(prec), 4) if prec is not None else None,
        "test_recall": round(float(rec), 4) if rec is not None else None,
        "test_f1": round(float(f1), 4) if f1 is not None else None,
        "test_n_pos": int(test_labels.sum()), "test_n": int(len(test_labels)),
        "test_tp": int(tp), "test_fp": int(fp), "test_fn": int(fn),
    }

item4 = {}
item4["walmart_amazon"] = title_sim_analysis("Walmart-Amazon", "title", "title",
    f"{BM}/Walmart-Amazon/source_source.parquet", f"{BM}/Walmart-Amazon/target_target.parquet",
    f"{BM}/Walmart-Amazon/pairs_train.parquet", f"{BM}/Walmart-Amazon/pairs_valid.parquet", f"{BM}/Walmart-Amazon/pairs_test.parquet")
item4["abt_buy"] = title_sim_analysis("Abt-Buy", "name", "name",
    f"{BM}/Abt-Buy/source_source.parquet", f"{BM}/Abt-Buy/target_target.parquet",
    f"{BM}/Abt-Buy/pairs_train.parquet", f"{BM}/Abt-Buy/pairs_valid.parquet", f"{BM}/Abt-Buy/pairs_test.parquet")
item4["amazon_google"] = title_sim_analysis("Amazon-Google", "title", "title",
    f"{BM}/Amazon-Google/source_source.parquet", f"{BM}/Amazon-Google/target_target.parquet",
    f"{BM}/Amazon-Google/pairs_train.parquet", f"{BM}/Amazon-Google/pairs_valid.parquet", f"{BM}/Amazon-Google/pairs_test.parquet")
results["item4"] = item4

# ---------- Item 5: price ----------
def price_analysis(name, s_path, t_path, train_p, valid_p, test_p):
    s_df = load(s_path).set_index("id"); t_df = load(t_path).set_index("id")
    pairs = pd.concat([load(train_p), load(valid_p), load(test_p)])
    rows = []
    for _, r in pairs.iterrows():
        sp = parse_price(s_df.loc[r["ltable_id"]]["price"])
        tp = parse_price(t_df.loc[r["rtable_id"]]["price"])
        rd = relative_price_diff(sp, tp)
        rows.append({"label": r["label"], "rd": rd})
    df = pd.DataFrame(rows)
    out = {}
    for lv in ["1","0"]:
        sub = df[(df["label"]==lv) & df["rd"].notna()]
        out["matched" if lv=="1" else "nonmatched"] = {
            "n_both_priced": len(sub),
            "n_total": int((df["label"]==lv).sum()),
            "quantiles": {f"p{q}": round(float(np.percentile(sub["rd"], q)),4) for q in [0,25,50,75,90,100]} if len(sub) else None,
            "pct_within_5pct": round((sub["rd"]<=0.05).mean()*100,2) if len(sub) else None,
            "pct_within_10pct": round((sub["rd"]<=0.10).mean()*100,2) if len(sub) else None,
        }
    return out

item5 = {}
item5["walmart_amazon"] = price_analysis("WA", f"{BM}/Walmart-Amazon/source_source.parquet", f"{BM}/Walmart-Amazon/target_target.parquet",
    f"{BM}/Walmart-Amazon/pairs_train.parquet", f"{BM}/Walmart-Amazon/pairs_valid.parquet", f"{BM}/Walmart-Amazon/pairs_test.parquet")
item5["abt_buy"] = price_analysis("AB", f"{BM}/Abt-Buy/source_source.parquet", f"{BM}/Abt-Buy/target_target.parquet",
    f"{BM}/Abt-Buy/pairs_train.parquet", f"{BM}/Abt-Buy/pairs_valid.parquet", f"{BM}/Abt-Buy/pairs_test.parquet")
item5["amazon_google"] = price_analysis("AG", f"{BM}/Amazon-Google/source_source.parquet", f"{BM}/Amazon-Google/target_target.parquet",
    f"{BM}/Amazon-Google/pairs_train.parquet", f"{BM}/Amazon-Google/pairs_valid.parquet", f"{BM}/Amazon-Google/pairs_test.parquet")
results["item5"] = item5

# ---------- Item 6: hard cases (Walmart-Amazon) ----------
wa_s_idx = wa_s.set_index("id"); wa_t_idx = wa_t.set_index("id")
hard = {"matched_low_sim_diff_model": [], "nonmatched_high_sim_or_equal_model": []}

wa_all_pairs["label"] = wa_all_pairs["label"].astype(str)
for _, r in wa_all_pairs.iterrows():
    srow = wa_s_idx.loc[r["ltable_id"]]; trow = wa_t_idx.loc[r["rtable_id"]]
    sim = jaccard(tokenize(srow["title"]), tokenize(trow["title"]))
    sm = normalize_modelno(srow["modelno"]); tm = normalize_modelno(trow["modelno"])
    model_equal = sm is not None and tm is not None and sm == tm
    if r["label"] == "1" and sim < 0.3 and not model_equal:
        hard["matched_low_sim_diff_model"].append({
            "lid": int(r["ltable_id"]), "rid": int(r["rtable_id"]),
            "s_title": srow["title"], "t_title": trow["title"],
            "s_model": srow["modelno"], "t_model": trow["modelno"], "jaccard": round(sim,3)
        })
    if r["label"] == "0" and (model_equal or sim > 0.6):
        hard["nonmatched_high_sim_or_equal_model"].append({
            "lid": int(r["ltable_id"]), "rid": int(r["rtable_id"]),
            "s_title": srow["title"], "t_title": trow["title"],
            "s_model": srow["modelno"], "t_model": trow["modelno"], "jaccard": round(sim,3)
        })

hard["matched_low_sim_diff_model"] = hard["matched_low_sim_diff_model"][:10]
hard["nonmatched_high_sim_or_equal_model"] = hard["nonmatched_high_sim_or_equal_model"][:10]
results["item6"] = hard

# ---------- Item 7: PriceRunner ----------
pr = load(f"{BM}/product-matching/default_train.parquet")
pr_item7 = {"n_rows": len(pr), "n_clusters": pr["Cluster ID"].nunique(), "n_vendors": pr["Vendor ID"].nunique()}
cluster_sizes = pr.groupby("Cluster ID").size()
pr_item7["cluster_size_quantiles"] = {f"p{q}": float(np.percentile(cluster_sizes,q)) for q in [0,25,50,75,90,99,100]}
pr_item7["cluster_size_mean"] = round(float(cluster_sizes.mean()),2)

# sample a few large clusters, show title variance and token stability
sample_clusters = cluster_sizes.sort_values(ascending=False).head(5).index.tolist()
examples = []
for cid in sample_clusters:
    sub = pr[pr["Cluster ID"]==cid]
    titles = sub["Product Title"].tolist()
    label = sub["Cluster Label"].iloc[0]
    all_token_sets = [tokenize(t) for t in titles]
    common = set.intersection(*all_token_sets) if all_token_sets else set()
    examples.append({"cluster_id": int(cid), "cluster_label": label, "n_offers": len(sub),
                      "sample_titles": titles[:8], "stable_tokens_across_all_offers": sorted(common)})
pr_item7["examples"] = examples

# language check: look for german-ish tokens
german_markers = ["spacegrau", "schwarz", "weiß", "grau", "silber", "grün", "blau", "rot", "édition", "édition"]
mask = pr["Product Title"].str.lower().apply(lambda t: any(m in t for m in german_markers) if isinstance(t,str) else False)
pr_item7["n_titles_with_german_markers"] = int(mask.sum())
pr_item7["sample_german_titles"] = pr.loc[mask, "Product Title"].head(8).tolist()
results["item7"] = pr_item7

# ---------- Item 8: ASIN-like ids check ----------
def asin_check():
    t = wa_t
    out = {}
    # ASIN pattern: 10 chars, alnum, often starts with B0
    asin_re_hits_id = t["id"].astype(str).str.match(r"^B0[A-Z0-9]{8}$").sum()
    asin_re_hits_model = t["modelno"].astype(str).str.match(r"^B0[A-Z0-9]{8}$").sum()
    out["id_col_sample"] = t["id"].astype(str).head(5).tolist()
    out["id_col_is_asin_like"] = int(asin_re_hits_id)
    out["modelno_asin_like_count"] = int(asin_re_hits_model)
    out["id_dtype_note"] = "id column is a plain row index (0..N-1), not an ASIN"
    return out
results["item8"] = asin_check()

with open("/tmp/_bench_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("DONE")
print(json.dumps({k: (v if k not in ("item6","item7") else "...") for k,v in results.items()}, indent=2, default=str)[:3000])
