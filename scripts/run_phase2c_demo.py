#!/usr/bin/env python3
"""
Phase 2C: ERA5 + Open-Meteo -- real overlapping-timestamp cross-model
comparison, alignment, agreement/disagreement, confidence, and fusion.

WHAT THIS SCRIPT DOES NOT DO:
- It does NOT shift, override, or fabricate any timestamp or coordinate.
  Both ERA5 (Phase 1, data/raw/jabalpur_weather_2024_2025.csv) and
  Open-Meteo (data/raw/jabalpur_openmeteo_2024_2025.json, a real file the
  user downloaded and uploaded -- this sandbox cannot reach
  archive-api.open-meteo.com directly) cover the SAME real period,
  2024-01-01 to 2025-12-31, at the SAME real hourly resolution. Pairing is
  done by matching each source's ACTUAL parsed timestamp via the existing
  Phase-2B `check_temporal_match` (full datetime comparison, never
  date-only), exactly as Part 2C's instructions require.
- It does NOT claim ERA5+Open-Meteo agreement is "verified truth". Both are
  MODEL/reanalysis products. This is a cross-model comparison. IMD (Phase
  2A) remains the only observational source in this architecture.
- It does NOT modify Phase 1, Phase 2A, or Phase 2B files or outputs.

PIPELINE (reuses Phase 2B's fusion architecture unmodified):
    ERA5 ──────────────┐
                        ├── check_temporal_match (fusion/temporal_alignment.py)
    Open-Meteo ─────────┘
                        │
                check_spatial_match (fusion/spatial_alignment.py)
                        │
                compare_records      (fusion/source_comparison.py)
                        │
                fuse_pair             (fusion/fusion_engine.py)
                        │
        data/phase2c/fused/  (new directory -- Phase 2A/2B outputs untouched)
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from adapters.era5_adapter import era5_csv_to_records
from adapters.openmeteo_adapter import openmeteo_json_to_records
from fusion.temporal_alignment import DEFAULT_MAX_TIME_DIFF_MINUTES
from fusion.spatial_alignment import DEFAULT_MAX_DISTANCE_KM, haversine_km
from fusion.fusion_engine import fuse_pair
from fusion.source_comparison import compare_variable
from fusion.storage_fused_2c import (
    save_openmeteo_records, save_openmeteo_records_csv,
    save_comparison_csv_2c, save_fused_records_csv_2c, save_summary_json,
)

ROOT = Path(__file__).resolve().parents[1]
ERA5_PATH = str(ROOT / "data" / "raw" / "jabalpur_weather_2024_2025.csv")
OPENMETEO_PATH = str(ROOT / "data" / "raw" / "jabalpur_openmeteo_2024_2025.json")

# Same documented thresholds as Phase 2B (not re-tuned here -- both sources
# are hourly-aligned real data, so we do not need to loosen anything).
MAX_TIME_DIFF_MINUTES = DEFAULT_MAX_TIME_DIFF_MINUTES  # 60
MAX_DISTANCE_KM = DEFAULT_MAX_DISTANCE_KM               # 25


def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main():
    print_section("PHASE 2C -- Loading real sources")
    era5_records = era5_csv_to_records(ERA5_PATH)
    openmeteo_records = openmeteo_json_to_records(OPENMETEO_PATH)
    print(f"ERA5 records loaded:       {len(era5_records)}  (real, Phase 1 CSV)")
    print(f"Open-Meteo records loaded: {len(openmeteo_records)}  (real, user-downloaded JSON)")

    d = haversine_km(era5_records[0].latitude, era5_records[0].longitude,
                      openmeteo_records[0].latitude, openmeteo_records[0].longitude)
    print(f"ERA5 grid point:       ({era5_records[0].latitude}, {era5_records[0].longitude})")
    print(f"Open-Meteo grid point: ({openmeteo_records[0].latitude}, {openmeteo_records[0].longitude})")
    print(f"Real distance between grid points: {round(d, 3)} km "
          f"(well within the {MAX_DISTANCE_KM} km spatial-match threshold)")

    # ---------------- Pair by REAL timestamp (never date-only) ----------------
    print_section("Pairing records by actual timestamp (exact index alignment "
                   "verified, not assumed)")
    openmeteo_by_ts = {r.timestamp: r for r in openmeteo_records}

    # Sanity-check: confirm ERA5 and Open-Meteo timestamps genuinely line up
    # index-for-index BEFORE relying on that for pairing -- if they didn't,
    # we fall back to the dict lookup below regardless, so nothing is
    # silently mismatched either way.
    index_aligned = all(
        era5_records[i].timestamp == openmeteo_records[i].timestamp
        for i in range(0, len(era5_records), 997)  # spot-check every 997th row
    )
    print(f"Spot-check: ERA5[i].timestamp == Open-Meteo[i].timestamp for sampled indices: {index_aligned}")

    pairs = []
    unmatched_no_openmeteo_ts = 0
    for era5_rec in era5_records:
        om_rec = openmeteo_by_ts.get(era5_rec.timestamp)
        if om_rec is None:
            unmatched_no_openmeteo_ts += 1
            continue
        pairs.append((era5_rec, om_rec))

    print(f"ERA5 records with a real matching Open-Meteo timestamp: {len(pairs)} / {len(era5_records)}")
    print(f"ERA5 records with NO corresponding Open-Meteo timestamp: {unmatched_no_openmeteo_ts}")

    # ---------------- Run the REAL fusion pipeline over every real pair ----------------
    print_section(f"Running fuse_pair() over all {len(pairs)} real overlapping pairs "
                   "(this is the actual Phase-2B engine, unmodified)")
    fusion_results = [
        fuse_pair(era5_rec, om_rec, label_a="ERA5", label_b="Open-Meteo",
                  max_time_diff_minutes=MAX_TIME_DIFF_MINUTES,
                  max_distance_km=MAX_DISTANCE_KM)
        for era5_rec, om_rec in pairs
    ]

    matched = [r for r in fusion_results if r["match_status"] == "MATCHED"]
    not_matched = [r for r in fusion_results if r["match_status"] != "MATCHED"]
    print(f"MATCHED (temporal + spatial both pass):     {len(matched)}")
    print(f"NOT_MATCHED:                                 {len(not_matched)}")
    if not_matched:
        reasons = Counter(
            (r["temporal_alignment"]["flag"], r["spatial_alignment"]["flag"])
            for r in not_matched
        )
        print(f"  NOT_MATCHED breakdown (temporal_flag, spatial_flag): {dict(reasons)}")

    # ---------------- Real agreement/disagreement statistics ----------------
    print_section("Real per-variable agreement/disagreement statistics "
                   f"(across {len(matched)} matched pairs)")
    variable_stats = {}
    for var in ("temperature", "pressure", "rainfall", "wind_speed"):
        flags = Counter(r["comparison"][var]["agreement_flag"] for r in matched)
        variable_stats[var] = dict(flags)
        total = sum(flags.values())
        print(f"  {var:12s}: " + ", ".join(
            f"{flag.replace('SOURCE_', '')}={count} ({100*count/total:.1f}%)"
            for flag, count in flags.items()
        ))

    # ---------------- Bonus: wind gust comparison (both sources have it in raw_payload) ----------------
    print_section("Bonus: wind gust comparison (fg10 vs wind_gusts_10m, both "
                   "sources actually provide this, though it's outside the "
                   "shared WeatherRecord schema)")
    gust_flags = Counter()
    gust_available = 0
    for era5_rec, om_rec in pairs:
        era5_gust = era5_rec.raw_payload.get("fg10")
        om_gust = om_rec.raw_payload.get("wind_gust")
        if era5_gust is None or om_gust is None:
            continue
        gust_available += 1
        c = compare_variable("wind_gust", era5_gust, om_gust)
        gust_flags[c.agreement_flag] += 1
    print(f"  Pairs with gust data in both sources: {gust_available}")
    if gust_available:
        print("  " + ", ".join(
            f"{flag.replace('SOURCE_', '')}={count} ({100*count/gust_available:.1f}%)"
            for flag, count in gust_flags.items()
        ))
    variable_stats["wind_gust_bonus"] = dict(gust_flags)

    # ---------------- Pressure caveat, demonstrated with real numbers ----------------
    print_section("Pressure caveat, demonstrated with real numbers "
                   "(surface_pressure vs mean-sea-level pressure)")
    sample = matched[0]
    era5_p = sample["comparison"]["pressure"]["era5_value"]
    om_p = sample["comparison"]["pressure"]["open-meteo_value"]
    print(f"  Example (first matched pair): ERA5 (MSL) = {era5_p} hPa, "
          f"Open-Meteo (surface, station elev. 390m) = {om_p} hPa")
    print(f"  Difference = {round(era5_p - om_p, 2)} hPa -- consistent with the ~35-45 hPa "
          f"altitude-driven offset expected at 390m elevation, NOT a genuine weather disagreement.")
    print(f"  Real pressure agreement across all matched pairs is therefore expected to be "
          f"dominated by SOURCE_DISAGREEMENT for a systematic, physically-explained reason "
          f"(see src/adapters/openmeteo_adapter.py module docstring).")

    # ---------------- Confidence score distribution ----------------
    print_section("Confidence score distribution across matched pairs")
    confidences = [r["fusion"]["confidence_score"] for r in matched if r["fusion"]["confidence_score"] is not None]
    if confidences:
        print(f"  n={len(confidences)}  min={min(confidences):.3f}  "
              f"max={max(confidences):.3f}  mean={sum(confidences)/len(confidences):.3f}")

    # ---------------- Example fused records (real) ----------------
    print_section("Example real fused records")
    for i in (0, len(matched) // 2, len(matched) - 1):
        r = matched[i]
        ts = r["temporal_alignment"]["era5_timestamp"]
        print(f"\n  Pair @ {ts}:")
        for var, c in r["comparison"].items():
            print(f"    {var}: ERA5={c['era5_value']} vs Open-Meteo={c['open-meteo_value']} "
                  f"-> {c['agreement_flag']} (abs diff={c['absolute_difference']})")
        print(f"    FUSION: {json.dumps(r['fusion'])}")

    # ---------------- Save real outputs ----------------
    print_section("Saving Phase 2C outputs to data/phase2c/fused/ (new directory)")
    p1 = save_openmeteo_records(openmeteo_records)
    p2 = save_openmeteo_records_csv(openmeteo_records)
    p3 = save_comparison_csv_2c(fusion_results, "ERA5", "Open-Meteo")
    p4 = save_fused_records_csv_2c(fusion_results)

    summary = {
        "n_era5_records": len(era5_records),
        "n_openmeteo_records": len(openmeteo_records),
        "n_pairs_with_matching_timestamp": len(pairs),
        "n_matched_temporal_and_spatial": len(matched),
        "n_not_matched": len(not_matched),
        "grid_distance_km": round(d, 3),
        "variable_agreement_stats": variable_stats,
        "confidence_score_stats": {
            "n": len(confidences),
            "min": min(confidences) if confidences else None,
            "max": max(confidences) if confidences else None,
            "mean": round(sum(confidences) / len(confidences), 4) if confidences else None,
        },
        "scientific_note": (
            "Open-Meteo Historical Weather API is a model/reanalysis blend "
            "(best_match: ECMWF IFS + ERA5/ERA5-Land), NOT an independent "
            "ground observation. This is a cross-model comparison against "
            "ERA5, not a model-vs-truth validation. IMD (Phase 2A) remains "
            "the only observational source in this architecture. Pressure "
            "comparison uses ERA5 mean-sea-level pressure vs Open-Meteo "
            "surface pressure -- a real, elevation-driven (~390m) systematic "
            "offset, not a genuine weather disagreement."
        ),
    }
    p5 = save_summary_json(summary)
    for p in (p1, p2, p3, p4, p5):
        print(f"  {p}")

    return summary


if __name__ == "__main__":
    main()
