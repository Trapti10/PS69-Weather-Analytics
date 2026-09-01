#!/usr/bin/env python3
"""
Phase 3C demonstration: weather-report corroboration and verification
against real Phase 2B/2C weather evidence (ERA5 + Open-Meteo) plus the
Phase 2A IMD fixture where compatible.

Pipeline:
    Phase 3A reports (validated/normalized/deduplicated)
        -> Phase 3B intelligence (semantic similarity, event classification, risk)
        -> Phase 3C corroboration (event->evidence mapping, temporal+spatial
           matching against ERA5/Open-Meteo/IMD, evidence comparison)
        -> Explainable verification result (SUPPORTED / CONFLICTING /
           UNVERIFIED / INSUFFICIENT_EVIDENCE)

*** HONESTY NOTE, read before trusting any single number below ***
Phase 3A/3B's own synthetic fixture reports are dated 2026 (fabricated
posting times -- see data/phase3/fixtures/*.json's `posted_at`/`reported_at`
fields). The REAL evidence this project has (ERA5 + Open-Meteo) only covers
2024-01-01 to 2025-12-31. These two facts mean the real Phase 3A/3B fixture
reports, run through Phase 3C exactly as they are, CANNOT temporally overlap
the real evidence at all -- every one of them is expected to resolve to
INSUFFICIENT_EVIDENCE. This is not a Phase 3C bug; it is an honest, direct
consequence of Phase 3A's fixtures being demo data with no relationship to
the real 2024-2025 weather record. Part 2 below demonstrates the SAME Phase
3C logic actually reaching SUPPORTED/CONFLICTING/UNVERIFIED using a small,
clearly-labeled set of CONTROLLED EDGE-CASE FIXTURES timestamped inside the
real evidence window, exactly as the Phase 3C spec's Part 11 permits
("Fixtures may be used for controlled edge-case tests, but label them as
fixtures").
"""
import sys
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from adapters.social_report_adapter import social_fixture_to_reports
from adapters.citizen_report_adapter import citizen_fixture_to_reports
from ingestion.report_validators import validate_reports
from ingestion.report_normalizer import normalize_reports
from ingestion.report_dedup import detect_duplicates
from intelligence.report_intelligence import run_intelligence_pipeline
from schemas.weather_report import WeatherReport

from corroboration.report_correlator import build_default_evidence_sources, correlate_report
from corroboration.verification_engine import verify_report
from corroboration.corroboration_storage import (
    save_verification_results_json, save_verification_results_csv, save_verification_summary,
)


def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def run_full_phase3a_3b_pipeline():
    reports = social_fixture_to_reports() + citizen_fixture_to_reports()
    reports = validate_reports(reports)
    reports = normalize_reports(reports)
    reports = detect_duplicates(reports)
    result = run_intelligence_pipeline(reports)
    return result["reports"]


# ---------------------------------------------------------------------------
# Part 2: controlled edge-case fixtures, timestamped inside the REAL
# 2024-2025 evidence window, for demonstrating that Phase 3C's verification
# logic actually reaches SUPPORTED / CONFLICTING / UNVERIFIED when temporal
# overlap exists. These are hand-authored fixtures, NOT real reports of any
# kind -- clearly labeled below and in each object's metadata.
# ---------------------------------------------------------------------------
def build_controlled_edge_case_reports():
    edge_cases = [
        dict(report_id="EDGE_RAIN_SUPPORTED", event_type="RAINFALL",
             timestamp="2024-09-10T21:00:00Z", latitude=23.25, longitude=80.00,
             text="[FIXTURE] Heavy rainfall reported in Jabalpur."),
        dict(report_id="EDGE_RAIN_CONFLICTING", event_type="RAINFALL",
             timestamp="2024-01-15T09:00:00Z", latitude=23.25, longitude=80.00,
             text="[FIXTURE] Heavy rainfall reported in Jabalpur on a dry day."),
        dict(report_id="EDGE_HEATWAVE_SUPPORTED", event_type="HEATWAVE",
             timestamp="2024-06-01T12:00:00Z", latitude=23.25, longitude=80.00,
             text="[FIXTURE] Extreme heatwave conditions reported."),
        dict(report_id="EDGE_STRONGWIND_SUPPORTED", event_type="STRONG_WIND",
             timestamp=None, latitude=23.25, longitude=80.00,
             text="[FIXTURE] Strong wind reported (timestamp intentionally missing)."),
        dict(report_id="EDGE_MISSING_LOCATION", event_type="STRONG_WIND",
             timestamp="2024-06-01T12:00:00Z", latitude=None, longitude=None,
             text="[FIXTURE] Strong wind reported (location intentionally missing)."),
        dict(report_id="EDGE_FOG_AMBIGUOUS", event_type="FOG",
             timestamp="2024-01-01T03:00:00Z", latitude=23.25, longitude=80.00,
             text="[FIXTURE] Fog reported at dawn -- Open-Meteo humidity=80% falls in the "
                  "ambiguous band, demonstrating the weak-proxy-only FOG mapping."),
        dict(report_id="EDGE_FOG_SUPPORTED_WEAK", event_type="FOG",
             timestamp="2024-01-01T00:00:00Z", latitude=23.25, longitude=80.00,
             text="[FIXTURE] Fog reported at dawn -- Open-Meteo humidity=96% is high enough to "
                  "count as (weak) supporting evidence."),
        dict(report_id="EDGE_OUTSIDE_EVIDENCE_WINDOW", event_type="RAINFALL",
             timestamp="2026-07-14T10:32:00Z", latitude=23.1815, longitude=79.9864,
             text="[FIXTURE] Same timestamp style as the real Phase 3A fixtures (2026) -- "
                  "demonstrates the honest INSUFFICIENT_EVIDENCE finding described above."),
    ]
    reports = []
    for case in edge_cases:
        r = WeatherReport(
            report_id=case["report_id"],
            source_type="PUBLIC_DATASET",
            source_name="Phase3C_controlled_edge_case_fixture",
            event_type=case["event_type"],
            timestamp=case["timestamp"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            text=case["text"],
            verification_status="UNVERIFIED",
            raw_payload={"_synthetic_note": "SYNTHETIC/FIXTURE -- hand-authored Phase 3C edge case, not a real report."},
        )
        reports.append(r)
    return reports


def main():
    print_section("PHASE 3C -- Part 1: Real Phase 3A/3B synthetic fixture reports "
                   "vs. real Phase 2B/2C weather evidence")
    real_pipeline_reports = run_full_phase3a_3b_pipeline()
    evidence_sources = build_default_evidence_sources()
    print("Evidence sources loaded:")
    for name, src in evidence_sources.items():
        print(f"  {name:12s} [{src.data_label:8s}] {len(src.records)} records")

    part1_results = []
    for r in real_pipeline_reports:
        corr = correlate_report(r, evidence_sources)
        part1_results.append(verify_report(r, corr))

    status_counts = Counter(res["verification_status"] for res in part1_results)
    print(f"\nVerification status counts across {len(part1_results)} real Phase 3A/3B "
          f"fixture reports:")
    for status in ("SUPPORTED", "CONFLICTING", "UNVERIFIED", "INSUFFICIENT_EVIDENCE"):
        print(f"  {status:22s}: {status_counts.get(status, 0)}")
    print("\n*** Expected honest finding: these are all (or nearly all) "
          "INSUFFICIENT_EVIDENCE, because Phase 3A's fixtures are dated 2026 "
          "and the real evidence only covers 2024-2025 -- see this script's "
          "module docstring. ***")
    sample = part1_results[0]
    print(f"\nExample result ({sample['report_id']}):")
    print(f"  event_category={sample['event_category']}  status={sample['verification_status']}")
    print(f"  reasons={sample['verification_reasons']}")

    print_section("PHASE 3C -- Part 2: Controlled edge-case FIXTURES "
                   "(timestamped inside the real 2024-2025 evidence window)")
    edge_reports = build_controlled_edge_case_reports()
    part2_results = []
    for r in edge_reports:
        corr = correlate_report(r, evidence_sources)
        result = verify_report(r, corr)
        part2_results.append(result)
        print(f"  {r.report_id:28s} -> {result['verification_status']:22s} "
              f"score={result['evidence_support_score']}")
        for reason in result["verification_reasons"]:
            print(f"      - {reason}")

    print_section("Summary")
    all_results = part1_results + part2_results
    all_status_counts = Counter(res["verification_status"] for res in all_results)
    print(f"Total reports processed: {len(all_results)} "
          f"({len(part1_results)} real Phase 3A/3B fixtures + {len(part2_results)} controlled edge-case fixtures)")
    print(f"Combined verification status counts: {dict(all_status_counts)}")

    print_section("Saving Phase 3C outputs to data/phase3c/ (new directory)")
    p1 = save_verification_results_json(all_results)
    p2 = save_verification_results_csv(all_results)
    p3 = save_verification_summary(all_results)
    for p in (p1, p2, p3):
        print(f"  {p}")

    return {
        "part1_status_counts": dict(status_counts),
        "part2_status_counts": dict(Counter(res["verification_status"] for res in part2_results)),
        "combined_status_counts": dict(all_status_counts),
    }


if __name__ == "__main__":
    main()
