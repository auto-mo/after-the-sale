# SharkNinja matcher evaluation (blind labels)

Pairs: 145; unsure: 7 (excluded from metrics).

| Stratum | Matcher said | Pairs (labelled) | Truly same | Truly different | Accuracy of matcher decision |
|---|---|---|---|---|---|
| A_model_key | same | 40 | 40 | 0 | 40/40 (100%) |
| B_title_match | same | 26 | 20 | 6 | 20/26 (77%) |
| C_title_cluster | same | 15 | 10 | 5 | 10/15 (67%) |
| D_hard_negative | different | 40 | 23 | 17 | 17/40 (42%) |
| E_near_miss | different | 17 | 3 | 14 | 14/17 (82%) |

Pooled over the sample (not population rates, because strata are not proportional): precision 0.864, recall on sampled pairs 0.729 (tp 70, fp 11, fn 26, tn 31).

## Disagreements

- pair 5 [E_near_miss] matcher=diff, label=1 (high): B gives model QB1000 Master Prep 450W which matches A's unbadged title exactly.
- pair 7 [D_hard_negative] matcher=diff, label=1 (high): Same WS642 base model, BL vs GN are color suffixes.
- pair 10 [D_hard_negative] matcher=diff, label=1 (high): MC950ZSS and MC950Z share base model MC950, SS is a finish/color suffix.
- pair 15 [D_hard_negative] matcher=diff, label=1 (high): Same QU922Q APEX vacuum, QBL vs QBK are color suffixes.
- pair 18 [C_title_cluster] matcher=same, label=0 (medium): A is a bowl+blade kit for BL770/771/772/780; B is bowl-only for BL770/771/772/780CO, different accessory contents.
- pair 20 [D_hard_negative] matcher=diff, label=1 (high): Both titles state 'Model BL205' verbatim despite inconsistent model_name field on B.
- pair 26 [D_hard_negative] matcher=diff, label=1 (high): Both QB751Q Storm Blender, CN vs BL are color suffixes.
- pair 27 [D_hard_negative] matcher=diff, label=1 (high): Same HV306Q model, only color (Pink vs Black) differs.
- pair 33 [C_title_cluster] matcher=same, label=0 (high): Dust Cup Dirt Bin and Motorized Power Floor Nozzle are two different accessory types.
- pair 36 [C_title_cluster] matcher=same, label=0 (medium): Same C33000 base pans but bundled with different extra pieces (C30020 8-inch pan vs C30026 10.25-inch pan), different SKUs.
- pair 38 [B_title_match] matcher=same, label=0 (high): A is a food processor bowl+blade attachment kit; B is a BL770 power base motor replacement, different accessory types.
- pair 41 [D_hard_negative] matcher=diff, label=1 (high): Both QB751Q Storm Blender, PR vs BL are color suffixes.
- pair 49 [D_hard_negative] matcher=diff, label=1 (high): Both QB751Q Storm Blender, BK vs R are color suffixes.
- pair 50 [D_hard_negative] matcher=diff, label=1 (medium): Same Shark Rotator Powered Lift-Away Vacuum line as pair 13/44, differ only by color.
- pair 54 [D_hard_negative] matcher=diff, label=1 (high): Same CW102 PossiblePan base model, BL vs GN are color suffixes.
- pair 58 [D_hard_negative] matcher=diff, label=1 (high): Both RV852WVQ 'ION Robot Vacuum Cleaning System S87', differ only by color.
- pair 63 [C_title_cluster] matcher=same, label=0 (medium): Same cleanser product but different pack counts (3-pack vs 4-pack), a different purchasable unit.
- pair 64 [D_hard_negative] matcher=diff, label=1 (high): Identical GI468 Lightweight Professional Iron title, one new one refurbished.
- pair 65 [D_hard_negative] matcher=diff, label=1 (high): Same IF203Q base model, QBL vs QRD are color suffixes.
- pair 67 [D_hard_negative] matcher=diff, label=1 (high): Same S4701 base model, D suffix likely denotes a variant of the same product.
- pair 77 [B_title_match] matcher=same, label=0 (high): A is a 4-pack of pint lids only (accessory); B is a full NC301 CREAMi unit plus a 2-pack of pints.
- pair 90 [D_hard_negative] matcher=diff, label=1 (high): Both BL770 Mega Kitchen System with identical bundled accessories.
- pair 96 [D_hard_negative] matcher=diff, label=1 (high): Both RV852WVQ ION Robot Vacuum S87, differ only by color.
- pair 105 [C_title_cluster] matcher=same, label=0 (high): WDB2 is a brushroll-only 2-pack; WDB1F2 is a brushroll+filter bundle, different accessory contents.
- pair 106 [D_hard_negative] matcher=diff, label=1 (medium): Both appear to be the NV801 DuoClean Powered Lift Away Speed Vacuum, A gives the model explicitly and B's generic title matches.
- pair 107 [D_hard_negative] matcher=diff, label=1 (high): HP102PET and HP102PETPR share the HP102 base model, PR is a color/variant suffix.
- pair 108 [D_hard_negative] matcher=diff, label=1 (high): Both CS970Q Accutemp Slow Cooking System, SS vs FM are color suffixes.
- pair 110 [B_title_match] matcher=same, label=0 (high): A is a hose/handle replacement part; B is a full NV360 vacuum unit.
- pair 117 [D_hard_negative] matcher=diff, label=1 (high): Same CW102 PossiblePan base model, RD vs GN are color suffixes.
- pair 120 [B_title_match] matcher=same, label=0 (high): A is a water reservoir tank accessory; B is a full CF091 coffee bar unit.
- pair 121 [E_near_miss] matcher=diff, label=1 (medium): Both appear to be the same Rocket DeluxePro/Deluxe Ultra Light Upright line (B explicitly HV320), differing by color.
- pair 124 [D_hard_negative] matcher=diff, label=1 (high): Both RV852WVQ ION Robot Vacuum S87, differ only by color.
- pair 128 [B_title_match] matcher=same, label=0 (high): A is a pints/lids accessory pack only; B is a full NC299AMZ CREAMi unit plus the same accessory pack.
- pair 129 [D_hard_negative] matcher=diff, label=1 (medium): Both titled 'Shark Rocket Ultralight Upright Swivel Vacuum' referencing HV300, differ only by color.
- pair 137 [D_hard_negative] matcher=diff, label=1 (medium): Same XSB726N filter part number/description for SV70/SV75/SV726, differ only in that B specifies a 2-pack.
- pair 139 [B_title_match] matcher=same, label=0 (medium): AZ1002 and AZ1000 are different Shark APEX model numbers, not established as a simple color suffix of the same base model.
- pair 140 [E_near_miss] matcher=diff, label=1 (medium): Both are 40oz replacement bowls explicitly compatible with QB1000/QB1003/QB1004/QB1005, likely the same or interchangeable accessory.
