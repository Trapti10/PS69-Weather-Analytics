#!/usr/bin/env python3
"""
Phase 3A demonstration: multi-source weather REPORT ingestion.

Pipeline (per the Phase 3A spec):
    Raw source (synthetic fixture)
        -> Source adapter (social_report_adapter / citizen_report_adapter)
        -> WeatherReport
        -> Validation      (report_validators.validate_report)
        -> Normalization   (report_normalizer.normalize_report)
        -> Deduplication prep (report_dedup.detect_duplicates)
        -> Processed reports (report_storage)

*** HONESTY NOTE ***
This script does NOT access any real social media or citizen-reporting
platform. Both fixtures are clearly labeled SYNTHETIC/DEMO DATA (see the
`_synthetic_note` field preserved in every report's `raw_payload`). No
real people, accounts, GPS traces, images, or videos are represented.
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
from ingestion.report_storage import save_reports_json, save_reports_csv


def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main():
    print_section("PHASE 3A -- Loading synthetic/demo sources "
                   "(NO live social media or citizen-app access)")
    social_reports = social_fixture_to_reports()
    citizen_reports = citizen_fixture_to_reports()
    print(f"Social-media fixture reports loaded:  {len(social_reports)}  (SYNTHETIC)")
    print(f"Citizen-report fixture reports loaded: {len(citizen_reports)}  (SYNTHETIC)")

    all_reports = social_reports + citizen_reports

    # ---------------- Validation ----------------
    print_section("Validation")
    all_reports = validate_reports(all_reports)
    for r in all_reports:
        flag_str = f" [{', '.join(r.quality_flags)}]" if r.quality_flags else ""
        print(f"  {r.report_id[:8]} ({r.source_type:14s}) -> {r.verification_status:10s}{flag_str}")

    # ---------------- Normalization ----------------
    print_section("Normalization (timestamp/text/place standardization, "
                   "baseline source_reliability assignment)")
    all_reports = normalize_reports(all_reports)
    for r in all_reports[:3]:
        print(f"  {r.report_id[:8]}: timestamp={r.timestamp} city={r.city} "
              f"state={r.state} reliability={r.source_reliability}")
    print(f"  ... ({len(all_reports)} total reports normalized)")

    # ---------------- Deduplication ----------------
    print_section("Deterministic deduplication "
                   "(exact-normalized-text + time-bucket + location-bucket + event_type)")
    all_reports = detect_duplicates(all_reports)
    for r in all_reports:
        dup_str = f"DUPLICATE of group {r.duplicate_group_id[:8]}" if r.is_duplicate else "original"
        print(f"  {r.report_id[:8]} \"{(r.text or '')[:50]}\" -> {dup_str}")

    # ---------------- Summary ----------------
    print_section("Summary")
    n_total = len(all_reports)
    n_social = len(social_reports)
    n_citizen = len(citizen_reports)
    n_rejected = sum(1 for r in all_reports if r.verification_status == "REJECTED")
    n_valid = n_total - n_rejected
    n_duplicates = sum(1 for r in all_reports if r.is_duplicate)
    n_unverified = sum(1 for r in all_reports if r.verification_status == "UNVERIFIED")
    n_suspicious = sum(1 for r in all_reports if r.verification_status == "SUSPICIOUS")
    event_counts = Counter(r.event_type for r in all_reports)
    location_counts = Counter(f"{r.city}, {r.state}" for r in all_reports if r.city or r.state)

    print(f"Total reports:      {n_total}")
    print(f"  Social media:     {n_social}")
    print(f"  Citizen reports:  {n_citizen}")
    print(f"Valid:              {n_valid}")
    print(f"Invalid (REJECTED): {n_rejected}")
    print(f"Duplicates:         {n_duplicates}")
    print(f"Unverified:         {n_unverified}")
    print(f"Suspicious:         {n_suspicious}")
    print(f"Event categories:   {dict(event_counts)}")
    print(f"Locations:          {dict(location_counts)}")

    # ---------------- Save ----------------
    print_section("Saving Phase 3A outputs to data/phase3/processed/ (new directory)")
    p1 = save_reports_json(all_reports, "all_weather_reports.json")
    p2 = save_reports_csv(all_reports, "all_weather_reports.csv")
    p3 = save_reports_json(social_reports, "social_weather_reports_processed.json")
    p4 = save_reports_json(citizen_reports, "citizen_weather_reports_processed.json")
    for p in (p1, p2, p3, p4):
        print(f"  {p}")

    return {
        "n_total": n_total, "n_social": n_social, "n_citizen": n_citizen,
        "n_valid": n_valid, "n_rejected": n_rejected, "n_duplicates": n_duplicates,
        "n_unverified": n_unverified, "n_suspicious": n_suspicious,
        "event_counts": dict(event_counts), "location_counts": dict(location_counts),
    }


if __name__ == "__main__":
    main()
