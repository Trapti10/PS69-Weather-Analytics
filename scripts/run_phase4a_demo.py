#!/usr/bin/env python3
"""
Phase 4A demonstration: unified Weather Intelligence records built from
REAL Phase 2B/2C fusion inputs and REAL Phase 3C corroboration output.

WHAT THIS SCRIPT DOES NOT DO:
- It does NOT re-run or modify Phase 2B/2C/3C's own logic. It calls
  fusion.fusion_engine.fuse_pair() (already generic, already used by
  Phase 2C for a non-ERA5/IMD pairing) on real ERA5 + real Open-Meteo
  records already sitting on disk, and reads Phase 3C's own
  data/phase3c/corroborated_reports.json exactly as Phase 3C wrote it.
- It does NOT fabricate any weather value, timestamp, or verification
  result. Every ERA5/Open-Meteo record used below is a real row from the
  real 17,544-record 2024-2025 series; every verification result is one
  Phase 3C already computed and saved.

WHY THESE FIVE TIMESTAMPS: Phase 3C's own demo (scripts/run_phase3c_demo.py)
produced exactly 5 reports that reached a real verification_status other
than INSUFFICIENT_EVIDENCE (see README "Phase 3C" section) -- all 5 are
Phase 3C's own controlled edge-case fixtures, deliberately timestamped
inside the real 2024-2025 evidence window at the real Jabalpur ERA5
gridpoint (23.25, 80.00) specifically so this kind of end-to-end
demonstration would be possible. This script fuses the real ERA5+Open-Meteo
evidence at those same 5 real timestamps and attaches the already-computed
Phase 3C verdicts to show the full pipeline end to end. It does NOT
demonstrate Phase 4A at full 17,544-record scale -- see Known Limitations.

PIPELINE:
    ERA5 (real, data/phase2/fused/era5_weather_records.json)
    Open-Meteo (real, data/phase2c/fused/openmeteo_weather_records.json)
        -> fuse_pair() (Phase 2B's own fusion engine, unmodified)
    Phase 3C corroboration (real, data/phase3c/corroborated_reports.json)
        -> select_report_evidence() (reuses Phase 2B's alignment functions)
        -> build_weather_intelligence()
        -> data/phase4/ (new directory -- no earlier phase's output touched)
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from schemas.weather_record import WeatherRecord
from fusion.fusion_engine import fuse_pair
from phase4.weather_intelligence import build_weather_intelligence
from phase4.intelligence_storage import save_weather_intelligence_json, save_weather_intelligence_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def load_records(path: Path):
    with open(path, "r") as f:
        raw = json.load(f)
    return [WeatherRecord(**item) for item in raw]


def main():
    print_section("PHASE 4A DEMO -- Unified Weather Intelligence (real data)")

    era5_records = load_records(PROJECT_ROOT / "data" / "phase2" / "fused" / "era5_weather_records.json")
    om_records = load_records(PROJECT_ROOT / "data" / "phase2c" / "fused" / "openmeteo_weather_records.json")
    era5_by_ts = {r.timestamp: r for r in era5_records}
    om_by_ts = {r.timestamp: r for r in om_records}

    with open(PROJECT_ROOT / "data" / "phase3c" / "corroborated_reports.json", "r") as f:
        verification_results = json.load(f)

    print(f"Loaded {len(era5_records)} real ERA5 records, {len(om_records)} real Open-Meteo records, "
          f"{len(verification_results)} real Phase 3C verification results.")

    # The 5 real timestamps where Phase 3C's own demo actually produced
    # non-INSUFFICIENT_EVIDENCE verdicts (see module docstring above).
    target_timestamps = sorted({
        r["report_timestamp"] for r in verification_results
        if r["verification_status"] != "INSUFFICIENT_EVIDENCE" and r.get("report_timestamp")
    })

    records = []
    skipped = []
    for ts in target_timestamps:
        era5_rec = era5_by_ts.get(ts)
        om_rec = om_by_ts.get(ts)
        if era5_rec is None or om_rec is None:
            skipped.append(ts)
            continue
        fusion_result = fuse_pair(era5_rec, om_rec, label_a="ERA5", label_b="Open-Meteo")
        wi = build_weather_intelligence(fusion_result=fusion_result, verification_results=verification_results)
        records.append(wi)

    if skipped:
        print(f"Skipped {len(skipped)} timestamp(s) with no matching real ERA5/Open-Meteo record: {skipped}")

    print_section("Results")
    for wi in records:
        print(f"{wi.timestamp}  sources={wi.contributing_sources}  "
              f"source_agreement={wi.source_agreement_confidence}  "
              f"corroboration={wi.corroboration_status}  "
              f"evidence_support={wi.evidence_support_score}  "
              f"overall_confidence={wi.overall_confidence}")

    status_counts = Counter(wi.corroboration_status for wi in records)
    print(f"\nCorroboration status counts: {dict(status_counts)}")

    json_path = save_weather_intelligence_json(records)
    csv_path = save_weather_intelligence_csv(records)
    print(f"\nSaved {len(records)} WeatherIntelligence records to:\n  {json_path}\n  {csv_path}")

    print_section("Known limitation, stated plainly")
    print(
        "This demo builds real fused WeatherIntelligence records only at the 5 real timestamps\n"
        "where Phase 3C's own demo happened to produce non-INSUFFICIENT_EVIDENCE report evidence\n"
        "(all 5 are Phase 3C's controlled edge-case fixtures, not real citizen/social reports --\n"
        "see README's Phase 3C section). It does not run Phase 4A across all 17,544 real\n"
        "ERA5/Open-Meteo hourly pairs, which would be straightforward (loop + fuse_pair, exactly\n"
        "as done here) but was out of scope for a demonstration script. See\n"
        "tests/test_phase4a_intelligence.py for full unit coverage of every corroboration/\n"
        "confidence code path using synthetic fixtures."
    )


if __name__ == "__main__":
    main()
