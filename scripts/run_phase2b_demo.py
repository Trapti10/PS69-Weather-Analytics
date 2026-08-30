#!/usr/bin/env python3
"""
Phase 2B demonstration: ERA5 + IMD -> temporal alignment -> spatial alignment
-> comparison -> agreement/disagreement -> confidence -> fused record.

HONESTY NOTE (read this before reading the output):
Real ERA5 data (Phase 1) covers 2024-01-01 to 2025-12-31.
The real IMD fixture (Phase 2A) is dated at fixture-creation time (2026-08-29),
since it's a fixture for offline testing, not a live pull for a historical date.
These two real datasets do not naturally share a time window.

This script demonstrates the fusion mechanism honestly in two parts:
  PART A: an authentic, unmodified pairing (real ERA5 timestamp vs. real IMD
          fixture timestamp) -- correctly reports TEMPORAL_MISMATCH. This is
          the true, unmodified behavior of the system on the data we actually
          have, shown first so it isn't hidden.
  PART B: for illustrating the MATCHED/agreement/disagreement/fusion paths
          that Part 1 alone cannot reach with our current data, this script
          clones the real IMD record and ONLY OVERRIDES ITS TIMESTAMP AND
          COORDINATES to align with a chosen ERA5 record, clearly labelled
          "SYNTHETIC PAIRING FOR DEMONSTRATION". The measurement VALUES
          (temperature, pressure, wind, rainfall) are the real fixture
          values -- untouched. A second synthetic pairing then perturbs the
          temperature value explicitly to demonstrate the disagreement path.
Nothing in this script is presented as a genuine historical observation.
"""
import sys
import json
import copy
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from adapters.era5_adapter import era5_csv_to_records
from ingestion.imd_client import IMDClient
from ingestion.validators import process_raw_records
from fusion.fusion_engine import fuse_pair
from fusion.storage_fused import (
    save_era5_records, save_era5_records_csv,
    save_comparison_csv, save_fused_records, save_fused_records_csv,
)

ERA5_PATH = str(Path(__file__).resolve().parents[1] / "data" / "raw" / "jabalpur_weather_2024_2025.csv")


def load_sources():
    era5_records = era5_csv_to_records(ERA5_PATH)
    client = IMDClient(use_fixtures=True)
    raw_imd = client.get_current_weather("42182")
    imd_records = process_raw_records(raw_imd, endpoint="current_wx")
    return era5_records, imd_records


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    era5_records, imd_records = load_sources()
    real_imd = imd_records[0]
    # Pick a representative ERA5 record for the demo (first record at hour 06)
    demo_era5 = next(r for r in era5_records if r.timestamp.endswith("06:00:00Z"))

    all_fusion_results = []

    # ---------------- PART A: authentic, unmodified pairing ----------------
    print_section("PART A -- Authentic pairing (real ERA5 timestamp, real IMD fixture timestamp)")
    print(f"ERA5 timestamp: {demo_era5.timestamp}  (real Phase-1 data)")
    print(f"IMD timestamp:  {real_imd.timestamp}  (real Phase-2A fixture, dated at fixture-creation time)")
    result_a = fuse_pair(demo_era5, real_imd, max_time_diff_minutes=60, max_distance_km=25)
    print(f"\nResult: match_status = {result_a['match_status']}")
    print(f"  temporal: {result_a['temporal_alignment']['flag']} "
          f"(diff = {result_a['temporal_alignment']['time_difference_minutes']} minutes)")
    print(f"  spatial:  {result_a['spatial_alignment']['flag']} "
          f"(IMD fixture carries no lat/lon, so this is SPATIAL_UNKNOWN, honestly)")
    print(f"  fusion:   {result_a['fusion']['note']}")
    all_fusion_results.append(result_a)

    # ---------------- PART B1: synthetic pairing -- agreement ----------------
    print_section("PART B1 -- SYNTHETIC PAIRING FOR DEMONSTRATION (timestamp/coords overridden, values real)")
    synthetic_imd_agree = copy.deepcopy(real_imd)
    synthetic_imd_agree.timestamp = demo_era5.timestamp          # overridden for demo
    synthetic_imd_agree.latitude = 23.18                          # overridden: nearby demo coordinate
    synthetic_imd_agree.longitude = 79.95                         # overridden: nearby demo coordinate
    # temperature/pressure/wind/rainfall are UNCHANGED real fixture values (29.4C, 1005.2hPa, etc.)

    print(f"ERA5: {demo_era5.timestamp} | temp={demo_era5.temperature}C | pressure={demo_era5.pressure}hPa")
    print(f"IMD (synthetic timestamp/coords, real values): {synthetic_imd_agree.timestamp} | "
          f"temp={synthetic_imd_agree.temperature}C | pressure={synthetic_imd_agree.pressure}hPa")

    result_b1 = fuse_pair(demo_era5, synthetic_imd_agree, max_time_diff_minutes=60, max_distance_km=25)
    print(f"\nResult: match_status = {result_b1['match_status']}")
    print(f"  temporal: {result_b1['temporal_alignment']['flag']} "
          f"(diff = {result_b1['temporal_alignment']['time_difference_minutes']} min)")
    print(f"  spatial:  {result_b1['spatial_alignment']['flag']} "
          f"(distance = {result_b1['spatial_alignment']['distance_km']} km)")
    for var, c in result_b1["comparison"].items():
        print(f"  {var}: ERA5={c['era5_value']} vs IMD={c['imd_value']} "
              f"-> {c['agreement_flag']} (abs diff={c['absolute_difference']})")
    print(f"  FUSION: {json.dumps({k: v for k, v in result_b1['fusion'].items()})}")
    all_fusion_results.append(result_b1)

    # ---------------- PART B2: synthetic pairing -- disagreement ----------------
    print_section("PART B2 -- SYNTHETIC PAIRING FOR DEMONSTRATION (temperature deliberately perturbed)")
    synthetic_imd_disagree = copy.deepcopy(synthetic_imd_agree)
    original_temp = synthetic_imd_disagree.temperature
    synthetic_imd_disagree.temperature = demo_era5.temperature + 8.0  # deliberately large gap
    print(f"ERA5 temperature: {demo_era5.temperature}C")
    print(f"IMD temperature (PERTURBED from real {original_temp}C for this demo): "
          f"{synthetic_imd_disagree.temperature}C")

    result_b2 = fuse_pair(demo_era5, synthetic_imd_disagree, max_time_diff_minutes=60, max_distance_km=25)
    temp_comparison = result_b2["comparison"]["temperature"]
    print(f"\nResult: {temp_comparison['agreement_flag']} "
          f"(abs diff={temp_comparison['absolute_difference']}C)")
    print(f"  Fused temperature: {result_b2['fusion'].get('temperature')} "
          f"(None expected -- disagreement is NOT averaged, per Part 7)")
    print(f"  Overall confidence_score: {result_b2['fusion']['confidence_score']} "
          f"(lower than PART B1's, reflecting the disagreement)")
    all_fusion_results.append(result_b2)

    # ---------------- Save outputs ----------------
    print_section("Saving Phase 2B outputs to data/phase2/fused/")
    p1 = save_era5_records(era5_records)
    p2 = save_era5_records_csv(era5_records)
    p3 = save_comparison_csv(all_fusion_results)
    p4 = save_fused_records(all_fusion_results)
    p5 = save_fused_records_csv(all_fusion_results)
    for p in (p1, p2, p3, p4, p5):
        print(f"  {p}")


if __name__ == "__main__":
    main()
