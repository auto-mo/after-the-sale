# SharkNinja matcher evaluation (blind labels, set: sn_test)

Pairs: 123; unsure: 5 (excluded from metrics).

| Stratum | Matcher said | Pairs (labelled) | Truly same | Truly different | Accuracy of matcher decision |
|---|---|---|---|---|---|
| A_model_key | same 36 / diff 0 | 36 | 32 | 4 | 32/36 (89%) |
| B_title_match | same 14 / diff 1 | 15 | 13 | 2 | 12/15 (80%) |
| C_title_cluster | same 10 / diff 0 | 10 | 8 | 2 | 8/10 (80%) |
| D_hard_negative | same 1 / diff 39 | 40 | 2 | 38 | 39/40 (98%) |
| E_near_miss | same 0 / diff 17 | 17 | 3 | 14 | 14/17 (82%) |

Pooled over the sample (not population rates, because strata are not proportional): precision 0.869, recall on sampled pairs 0.914 (tp 53, fp 8, fn 5, tn 52).

## Disagreements

- pair 4 [A_model_key] matcher=same, label=0 (medium): EP033 vs EP033TN are different model numbers with differing feature descriptions; not a known colour/retailer suffix.
- pair 5 [B_title_match] matcher=same, label=0 (medium): A is Rocket PowerHead Upright (no model) vs B is NV480 Rocket Upright; different feature text, no shared model number.
- pair 12 [A_model_key] matcher=same, label=0 (medium): S3501 vs S3501N are different steam mop model numbers.
- pair 14 [C_title_cluster] matcher=same, label=0 (high): Bundle A includes a knife set (K32017) while bundle B includes a stock pot (C30465) - different bundle contents/SKUs despite shared cookware set.
- pair 17 [C_title_cluster] matcher=same, label=0 (medium): AF101 vs AF100 are different model numbers (different generation of Ninja air fryer).
- pair 23 [D_hard_negative] matcher=diff, label=1 (medium): Both titles reference IX141H Purple with identical feature text; B's item_model_number field (IX140H) appears to be a data entry inconsistency.
- pair 41 [A_model_key] matcher=same, label=0 (medium): B's title explicitly says HV302 (different model from HV301) despite the item_model_number field listing HV301, which appears to be a data error.
- pair 44 [E_near_miss] matcher=diff, label=1 (low): A is a generic 'Rocket Powerhead Vacuum Cleaner' (no model) and B is the specific AH452 Rocket PowerHead; plausible match on product name alone but no confirming fields.
- pair 85 [B_title_match] matcher=same, label=0 (high): A is a bowl/lid attachment compatible with BL200/BL201/BL204; B is the full BL201 blender/processor system - accessory vs main unit.
- pair 104 [E_near_miss] matcher=diff, label=1 (medium): A is a generic 'Nutri Bowl DUO Blender with Auto-iQ Boost' (no model) and B specifies model NN101 for the same product name; likely the same unit.
- pair 109 [B_title_match] matcher=diff, label=1 (high): Both are the identical Ninja Foodi Power Pitcher System (Ninja CO351B), identical feature text.
- pair 111 [A_model_key] matcher=same, label=0 (medium): S3601 vs S3601D are different model numbers for Shark Professional Steam Pocket Mop.
- pair 119 [E_near_miss] matcher=diff, label=1 (medium): A is a generic 'Rocket Ultra-Light Corded Stick Vacuum' (Black, no model) matching B's HV300 title phrase closely, though colour/model are unconfirmed.
