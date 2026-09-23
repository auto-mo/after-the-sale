# Benchmark matcher results

Weights and threshold tuned on train+valid only; metrics below are on the held-out **test** split.

## abt_buy
- tuned weights {'jac': 1.0, 'cross': 0.8, 'price': 0.25, 'brand': 0.1, 'num': 0.3}, threshold 0.34
- **test: precision 0.93, recall 0.777, F1 0.847** (tp 160, fp 12, fn 46, tn 1698)
- baseline model-number only: precision 1.0, recall 0.466, F1 0.636
- baseline title overlap only (best threshold chosen on test, so optimistic): F1 0.503
- decision path on test pairs: {'model_conflict': 912, 'blended': 895, 'model_equal': 96, 'model_prefix': 13}

## amazon_google
- tuned weights {'jac': 1.0, 'cross': 0.0, 'price': 0.4, 'brand': 0.2, 'num': 0.1}, threshold 0.52
- **test: precision 0.469, recall 0.543, F1 0.503** (tp 127, fp 144, fn 107, tn 1915)
- baseline model-number only: precision 0.35, recall 0.03, F1 0.055
- baseline title overlap only (best threshold chosen on test, so optimistic): F1 0.463
- decision path on test pairs: {'blended': 2246, 'model_conflict': 27, 'model_equal': 20}

## walmart_amazon
- tuned weights {'jac': 1.0, 'cross': 0.35, 'price': 0.15, 'brand': 0.0, 'num': 0.2}, threshold 0.58
- **test: precision 0.87, recall 0.834, F1 0.852** (tp 161, fp 24, fn 32, tn 1832)
- baseline model-number only: precision 0.992, recall 0.653, F1 0.787
- baseline title overlap only (best threshold chosen on test, so optimistic): F1 0.429
- decision path on test pairs: {'model_conflict': 1345, 'blended': 539, 'model_equal': 127, 'model_prefix': 19, 'model_contains': 10, 'model_in_other_title': 9}
