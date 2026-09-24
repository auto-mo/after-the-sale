"""Precision of each complaint theme, from a blind-labelled sample of 25 low-star SharkNinja reviews per theme (round 2 re-samples themes whose
rules were tightened after round 1).
eval/theme_sample.csv holds the sampled (review, theme) pairs; eval/theme_labels.csv the labels (1 = the review really
reports that problem). Writes eval/theme_precision.csv; themes under 0.7 belong in pipeline/themes.py WEAK_THEMES.
Run: .venv/bin/python eval/theme_eval.py"""
from pathlib import Path

import numpy as np
import pandas as pd

E = Path(__file__).resolve().parent
s = pd.read_csv(E / "theme_sample.csv").merge(pd.read_csv(E / "theme_labels.csv"), on="sample_id")
# Round 2: themes whose rules were tightened after round 1 are measured only on a fresh sample of the new rule.
if (E / "theme_labels_r2.csv").exists():
    s2 = pd.read_csv(E / "theme_sample_r2.csv").merge(pd.read_csv(E / "theme_labels_r2.csv"), on="sample_id")
    s = pd.concat([s[~s.theme.isin(set(s2.theme))], s2], ignore_index=True)
rng = np.random.default_rng(0)
rows = []
for theme, g in s.groupby("theme"):
    lab = g.label.values
    boot = [rng.choice(lab, len(lab)).mean() for _ in range(2000)]
    rows.append(dict(theme=theme, n=len(g), precision=lab.mean(), lo=np.percentile(boot, 5), hi=np.percentile(boot, 95)))
p = pd.DataFrame(rows).sort_values("precision", ascending=False)
p.to_csv(E / "theme_precision.csv", index=False)
print(p.round(2).to_string(index=False))
print(f"\nall themes: {s.label.mean():.2f} on {len(s)} labelled pairs; below 0.7: {', '.join(p[p.precision < 0.7].theme) or 'none'}")
