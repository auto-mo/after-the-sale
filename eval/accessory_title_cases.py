"""Fixed regression list for rules.is_accessory_title. Run: .venv/bin/python eval/accessory_title_cases.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import rules as R  # noqa: E402

UNITS = ["Shark UV540 Lift-Away Upright Vacuum (Renewed)", "Shark Navigator Lift-Away HEPA Filter Anti-Allergen Technology Corded Upright Vacuum",
         "Shark NV360 Navigator Lift-Away Deluxe Upright Vacuum with Large Dust Cup Capacity, HEPA Filter",
         "Shark IQ Robot Vacuum AV1010AE with XL Self-Empty Base, Multi-Surface Brushroll", "Shark DuoClean UV700 Self Cleaning Brushroll Lift-Away Vacuum with Zero-M",
         "Shark AV2001WD AI VACMOP 2-in-1 Robot Vacuum and Mop with Self-Cleaning Brushroll", "Ninja DCM201CP Programmable XL 14-Cup Coffee Maker PRO with Permanent Filter",
         "Shark HE401 Air Purifier with Anti-Allergen Multi-Filter", "Ninja Foodi 9-in-1 Pressure Cooker and Air Fryer with Nesting Broil Rack",
         "Ninja BL610 Professional 72 Oz Countertop Blender with 1000-Watt Base and Total Crushing Technology",
         "Shark Rocket Bagless Hand Vacuum HV294Q with Home and Car Detail Tool, Extended Reach Hose", "Nutri Ninja Nutri Bowl DUO with Auto-iQ Boost NN100A 1200-Watt Motor (Renewed)",
         "Ninja CF091 Coffee Bar, Black/Silver (Renewed)", "Ninja DZ201 Foodi 8 Quart 6-in-1 DualZone 2-Basket Air Fryer",
         "Shark HP102PETBL Clean Sense Air Purifier for Home, Allergies, Pet Hair, HEPA Filter",
         "Shark Rocket HV294Q Handheld Vacuum with Pet Multi-Tool Attachment"]
ACCS = ["AirMyFun Genuine Shark Hose Part 207FFJ360 Navigator Lift Away Vacuum Handle NV360, NV585", "Shark XSB726N Dust Cup Filters for SV75 SV70 SV726 Hand Vacs, 2 Pack",
        "Euro-Pro Shark Hand Vac Filter 18355", "Ninja Water Reservoir Tank 50 oz 101KKW090 Without Lid CF090 CF091", "Ninja BL770-PBM Power Base Motor Blender Replacement, Black",
        "Ninja Blender 64oz Food Processor Bowl Attachment Kit - BL770 BL780", "Shark Rotator Professional Lift-Away NV500 Series Dirt Bin, 1190FC500B",
        "Shark Genuine Navigator Dust Cup for Professional Lift-Away DLX Deluxe", "Nutri Ninja (16 oz Single Serve Cups with Lids for Ninja BL660, 2-Pack",
        "Shark Euro-Pro EP76, EP77 Canister Vacuum Cleaner Filters XSD76", "Ninja Auto-Spiralizer Accessory Kit - XSKSPIRALW2",
        "Shark Rotator Powered Lift-Away Speed NV681, NV682 Pet Hair Turbo Attachment, 188FLI680", "Shark Navigator Lift-Away Upright Vacuum Onboard Accessory Holder, Gray",
        "SHARK Shark VACMOP Disposable Hard Floor Vacuum and Mop Pad Refills (32 ct)", "Ninja 12-tablespoon Coffee and Bean Spices Grinder Attachment"]
bad = [("unit read as accessory", t) for t in UNITS if R.is_accessory_title(t)] + [("accessory missed", t) for t in ACCS if not R.is_accessory_title(t)]
print(f"{len(bad)} errors / {len(UNITS) + len(ACCS)} cases")
for k, t in bad:
    print(" ", k, "|", t)
sys.exit(1 if bad else 0)
