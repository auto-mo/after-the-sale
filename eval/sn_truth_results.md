# SharkNinja matcher evaluation (blind labels, set: sn_truth)

Pairs: 145; unsure: 7 (excluded from metrics).

| Stratum | Matcher said | Pairs (labelled) | Truly same | Truly different | Accuracy of matcher decision |
|---|---|---|---|---|---|
| A_model_key | same 37 / diff 3 | 40 | 40 | 0 | 37/40 (92%) |
| B_title_match | same 20 / diff 6 | 26 | 20 | 6 | 22/26 (85%) |
| C_title_cluster | same 11 / diff 4 | 15 | 10 | 5 | 12/15 (80%) |
| D_hard_negative | same 17 / diff 23 | 40 | 23 | 17 | 34/40 (85%) |
| E_near_miss | same 0 / diff 17 | 17 | 3 | 14 | 14/17 (82%) |

Pooled over the sample (not population rates, because strata are not proportional): precision 0.953, recall on sampled pairs 0.844 (tp 81, fp 4, fn 15, tn 38).

## Disagreements

- pair 5 [E_near_miss] matcher=diff, label=1 (high): B gives model QB1000 Master Prep 450W which matches A's unbadged title exactly.
- pair 15 [D_hard_negative] matcher=diff, label=1 (high): Same QU922Q APEX vacuum, QBL vs QBK are color suffixes.
- pair 36 [C_title_cluster] matcher=same, label=0 (medium): Same C33000 base pans but bundled with different extra pieces (C30020 8-inch pan vs C30026 10.25-inch pan), different SKUs.
- pair 39 [A_model_key] matcher=diff, label=1 (medium): Both are XSB726N Dust Cup Filters for the same SV70/SV75/SV726 hand vac line.
- pair 53 [B_title_match] matcher=diff, label=1 (high): Identical Foodi Power Pitcher System title; B explicitly confirms model Ninja CO351B.
- pair 58 [D_hard_negative] matcher=diff, label=1 (high): Both RV852WVQ 'ION Robot Vacuum Cleaning System S87', differ only by color.
- pair 63 [C_title_cluster] matcher=same, label=0 (medium): Same cleanser product but different pack counts (3-pack vs 4-pack), a different purchasable unit.
- pair 78 [A_model_key] matcher=diff, label=1 (high): Both AV1010AE IQ Robot Vacuum, same model number.
- pair 90 [D_hard_negative] matcher=diff, label=1 (high): Both BL770 Mega Kitchen System with identical bundled accessories.
- pair 106 [D_hard_negative] matcher=diff, label=1 (medium): Both appear to be the NV801 DuoClean Powered Lift Away Speed Vacuum, A gives the model explicitly and B's generic title matches.
- pair 121 [E_near_miss] matcher=diff, label=1 (medium): Both appear to be the same Rocket DeluxePro/Deluxe Ultra Light Upright line (B explicitly HV320), differing by color.
- pair 122 [B_title_match] matcher=diff, label=1 (high): Identical Foodi Power Pitcher System (CO351B) title on both sides.
- pair 123 [C_title_cluster] matcher=diff, label=1 (high): Both HZ2002/QS2000Q Shark Vertex Stick Vacuum, differ only by color.
- pair 128 [B_title_match] matcher=same, label=0 (high): A is a pints/lids accessory pack only; B is a full NC299AMZ CREAMi unit plus the same accessory pack.
- pair 129 [D_hard_negative] matcher=diff, label=1 (medium): Both titled 'Shark Rocket Ultralight Upright Swivel Vacuum' referencing HV300, differ only by color.
- pair 136 [A_model_key] matcher=diff, label=1 (high): Same AV2001WD base unit; B bundles extra towel/screen cleaner accessories.
- pair 137 [D_hard_negative] matcher=diff, label=1 (medium): Same XSB726N filter part number/description for SV70/SV75/SV726, differ only in that B specifies a 2-pack.
- pair 139 [B_title_match] matcher=same, label=0 (medium): AZ1002 and AZ1000 are different Shark APEX model numbers, not established as a simple color suffix of the same base model.
- pair 140 [E_near_miss] matcher=diff, label=1 (medium): Both are 40oz replacement bowls explicitly compatible with QB1000/QB1003/QB1004/QB1005, likely the same or interchangeable accessory.
