#!/usr/bin/env python3
"""
Phase 2 entry point: IMD ingestion -> validation -> standardized WeatherRecord -> storage.

Usage:
    python scripts/run_imd_ingestion.py --stations 42182 42809 --mode live
    python scripts/run_imd_ingestion.py --stations 42182 42809 --mode fixtures

`--mode fixtures` runs the full pipeline offline using the fixture files in
data/phase2/fixtures/ (see README for why: IMD's real-time endpoints require
IP whitelisting we don't have yet). `--mode live` calls the real IMD API and
will work as-is once whitelisting is granted -- no code changes needed.

For Phase 2 testing, use a SMALL number of station IDs (a handful), not an
attempt to cover all of India -- see README "Scaling to all India" section
for why and how that changes in later phases.
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from ingestion.imd_client import IMDClient, IMDAccessError
from ingestion.validators import process_raw_records
from ingestion.storage import save_raw, save_records_json, save_records_csv


def run(station_ids, mode: str):
    use_fixtures = (mode == "fixtures")
    client = IMDClient(use_fixtures=use_fixtures)

    all_records = []

    for station_id in station_ids:
        print(f"\n--- Fetching current_wx for station {station_id} (mode={mode}) ---")
        try:
            raw = client.get_current_weather(station_id)
        except IMDAccessError as e:
            print(f"[ACCESS ERROR] {e}")
            continue

        save_raw(raw, source_label=f"imd_current_wx_{station_id}")
        records = process_raw_records(raw, endpoint="current_wx")

        for r in records:
            print(f"  {r.station_id} | {r.city} | {r.timestamp} | "
                  f"temp={r.temperature}C | status={r.verification_status} "
                  f"| flags={r.quality_flags} | confidence={r.confidence_score}")

        all_records.extend(records)

    if all_records:
        json_path = save_records_json(all_records)
        csv_path = save_records_csv(all_records)
        print(f"\nSaved {len(all_records)} records to:")
        print(f"  {json_path}")
        print(f"  {csv_path}")
    else:
        print("\nNo records were ingested (all requests failed or returned empty).")

    return all_records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2 — IMD ingestion pipeline")
    parser.add_argument("--stations", nargs="+", default=["42182"],
                         help="IMD station IDs to fetch (small test set; see README)")
    parser.add_argument("--mode", choices=["live", "fixtures"], default="fixtures",
                         help="'live' calls the real IMD API (requires IP whitelisting); "
                              "'fixtures' runs the pipeline offline for testing/demo")
    args = parser.parse_args()

    run(args.stations, args.mode)
