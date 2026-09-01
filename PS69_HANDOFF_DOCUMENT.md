# PS69 — National Weather Big Data Analytics Platform (SIH 2026)
## Handoff Document — For a New Claude Session to Continue This Project

**Read this entire document before doing anything.** This project has strict conventions
(honesty about data provenance, append-only phase discipline, no fabrication) that must be
followed exactly, or you will break trust with the user and potentially corrupt a working,
fully-tested codebase.

---

## 0. How to Start a New Session on This Project

1. The user will upload the project as a `.zip` file (e.g. `PS69-Weather-Analytics_Phase_3A.zip`).
   Extract it and treat it as the ground truth — do not recreate anything from this document
   without first inspecting the actual files on disk.
2. Read this entire handoff document.
3. Before writing any new code, actually `view` the relevant existing files (schemas, adapters,
   fusion modules, validators) — this document summarizes them, but the real files are the source
   of truth and may have been updated since this document was written.
4. Run the full existing test suite first, to confirm the baseline is healthy, before adding
   anything new:
   ```bash
   python tests/test_phase2_ingestion.py
   python tests/test_phase2b_fusion.py
   python tests/test_phase2c_openmeteo.py
   python tests/test_phase3a_reports.py
   python tests/test_phase3b_intelligence.py
   python tests/test_phase3c_corroboration.py
   python tests/test_phase4a_intelligence.py
   ```
   Expected: **140 passed, 0 failed** (7 + 20 + 17 + 27 + 21 + 21 + 27), all offline, no network access needed.

---

## 1. The Non-Negotiable Rules of This Project

These have been followed strictly across every phase so far. Do not deviate.

1. **Append-only phase discipline.** Never modify, delete, or rename a file from a previously
   completed phase unless there is a clearly-disclosed, necessary reason (this has happened
   exactly once — see §4, Phase 2B's `validators.py` change — and it was explicitly flagged to
   the user before and after). New functionality goes in new files/modules.
2. **No fabricated data, ever.** If real data can't be obtained (e.g. a sandbox can't reach an
   external API), the correct move is: (a) tell the user honestly, (b) give them an exact,
   verified command to fetch it themselves, (c) wait for them to upload the real file. Never
   silently substitute synthetic data and call it real.
3. **Synthetic/demo data must be permanently, visibly labeled.** Any fixture or demo data must
   carry an explicit marker (e.g. `_synthetic_note` or `_fixture_note`) that survives into the
   final stored record's `raw_payload` — not just in a docstring — so a downstream consumer can
   always tell it's not real by inspecting the record itself.
4. **Document limitations instead of patching them away.** When a real methodological problem is
   discovered (e.g. Phase 2C's pressure-threshold masking, or Phase 3A's dedup blind spot on
   paraphrased duplicates), the correct move is to document it clearly, write a test that proves
   it's real and reproducible, and recommend a fix for a *future* phase — not to silently modify
   an earlier phase's code to hide it.
5. **Never silently discard invalid data.** Invalid/malformed records must be flagged (e.g.
   `REJECTED`, `SUSPICIOUS`) and still stored/counted, never dropped from the pipeline.
6. **Every claim of "X tests passing" must be from an actual run you just did.** Never report
   test results without having executed them in this session.
7. **Full disclosure format at the end of every phase.** Every phase's final response follows the
   same shape: files created, files modified (with justification if any), test results (actual
   numbers from an actual run), real output examples, scientific limitations, and a recommended
   next phase.

---

## 2. Project Structure (as of end of Phase 3C)

```
PS69-Weather-Analytics/
├── data/
│   ├── raw/                                   # Phase 1 + Phase 2C real source files
│   │   ├── jabalpur_weather_2024_2025.csv     # ERA5 (Copernicus CDS zip, .csv extension)
│   │   └── jabalpur_openmeteo_2024_2025.json  # Open-Meteo (real, user-downloaded)
│   ├── processed/                             # Phase 1: cleaned data, features, trained models
│   ├── phase2/
│   │   ├── fixtures/                          # Phase 2A: offline IMD test fixtures
│   │   ├── raw/                               # Phase 2A: raw IMD API pull audit trail
│   │   ├── processed/                         # Phase 2A: standardized IMD WeatherRecords
│   │   └── fused/                             # Phase 2B: ERA5+IMD fusion outputs
│   ├── phase2c/
│   │   └── fused/                             # Phase 2C: ERA5+Open-Meteo fusion outputs
│   ├── phase3/
│   │   ├── fixtures/                          # Phase 3A: SYNTHETIC social/citizen report fixtures
│   │   ├── raw/                               # Phase 3A: reserved for future real raw pulls
│   │   └── processed/                         # Phase 3A: normalized WeatherReport outputs
│   ├── phase3b/                                # Phase 3B: intelligence-enriched WeatherReport outputs
│   └── phase3c/                                # Phase 3C: corroboration/verification outputs
├── notebooks/                                  # Phase 1: 01–06, unchanged since Phase 1
├── models/phase3b/                             # Phase 3B: trained TF-IDF+LogReg classifier + metadata
├── src/
│   ├── data/, features/, evaluation/, models/  # Phase 1 modules, unchanged
│   ├── schemas/
│   │   ├── weather_record.py                   # Phase 2A+: structured met. OBSERVATIONS schema
│   │   └── weather_report.py                   # Phase 3A/3B: unstructured REPORTS schema (separate!)
│   ├── ingestion/
│   │   ├── imd_client.py, validators.py, storage.py    # Phase 2A (WeatherRecord side)
│   │   ├── report_validators.py                        # Phase 3A (WeatherReport side)
│   │   ├── report_normalizer.py                        # Phase 3A
│   │   ├── report_dedup.py                             # Phase 3A
│   │   └── report_storage.py                           # Phase 3A
│   ├── adapters/
│   │   ├── era5_adapter.py                     # Phase 2B
│   │   ├── openmeteo_adapter.py                # Phase 2C
│   │   ├── social_report_adapter.py            # Phase 3A (SYNTHETIC fixture-based)
│   │   └── citizen_report_adapter.py           # Phase 3A (SYNTHETIC fixture-based)
│   ├── fusion/
│   │   ├── temporal_alignment.py, spatial_alignment.py,
│   │   │   source_comparison.py, fusion_engine.py       # Phase 2B — fully generic, source-agnostic
│   │   ├── storage_fused.py                             # Phase 2B output writer (ERA5+IMD)
│   │   └── storage_fused_2c.py                          # Phase 2C output writer (ERA5+Open-Meteo)
│   ├── intelligence/
│   │   ├── semantic_similarity.py, event_classifier.py,
│   │   │   report_risk.py, report_intelligence.py       # Phase 3B
│   │   └── intelligence_storage.py                      # Phase 3B output writer
│   └── corroboration/                                    # Phase 3C package
│       ├── evidence_mapper.py         # event_type -> required/supporting/unavailable variables
│       ├── temporal_evidence.py       # reuses fusion.temporal_alignment, bisect-indexed lookup
│       ├── spatial_evidence.py        # reuses fusion.spatial_alignment, unmodified
│       ├── report_correlator.py       # loads ERA5/Open-Meteo/IMD evidence, finds best matches
│       ├── verification_engine.py     # ONLY module assigning a verification_status/score
│       └── corroboration_storage.py   # Phase 3C output writer
├── scripts/
│   ├── run_imd_ingestion.py                    # Phase 2A
│   ├── run_phase2b_demo.py                     # Phase 2B
│   ├── run_phase2c_demo.py                     # Phase 2C
│   ├── run_phase3a_demo.py                     # Phase 3A
│   ├── run_phase3b_demo.py                     # Phase 3B
│   └── run_phase3c_demo.py                     # Phase 3C
├── tests/
│   ├── test_phase2_ingestion.py       # 7 tests
│   ├── test_phase2b_fusion.py         # 20 tests
│   ├── test_phase2c_openmeteo.py      # 17 tests
│   ├── test_phase3a_reports.py        # 27 tests
│   ├── test_phase3b_intelligence.py   # 21 tests
│   └── test_phase3c_corroboration.py  # 21 tests
├── reports/findings.md              # Phase 1 findings
├── download_weather.py               # Phase 1: cdsapi ERA5 pull script
├── requirements.txt
└── README.md                         # Append-only; has a section per phase, in order
```

**Total: 140 tests passing, 0 failing, entirely offline** (113 through Phase 3C + 27 from Phase 4A,
see §9 — the tree above is unchanged from end-of-Phase-3C except for the new `src/phase4/`,
`scripts/run_phase4a_demo.py`, `tests/test_phase4a_intelligence.py`, and `data/phase4/`) (no live
network access needed to run
anything — all real data is already on disk, all synthetic data is in fixtures).

---

## 3. Phase-by-Phase Summary

### Phase 1 — ERA5 baseline (COMPLETE)
- Real ERA5 reanalysis data, Jabalpur (23.25°N, 80.00°E), hourly, 2024-01-01 to 2025-12-31
  (17,544 hourly records), downloaded via Copernicus CDS (`download_weather.py`).
- Pipeline: inspection → data-quality checks → cleaning/unit conversion → EDA → feature
  engineering → ML-problem selection → baseline modeling → time-series-aware evaluation.
- Selected problems: short-term temperature forecasting + rain occurrence classification.
- Strict rules followed: no random shuffling before splitting (chronological only), no data
  leakage (lag features use `.shift()`), no fabricated results.

### Phase 2A — IMD ingestion (COMPLETE, 7 tests)
- `src/schemas/weather_record.py` — the shared `WeatherRecord` dataclass used by every
  meteorological-observation source since (ERA5, IMD, Open-Meteo).
- `src/ingestion/imd_client.py` — real IMD API client. **Real, verified finding:** IMD's live
  `current_wx`/`aws_data` endpoints return HTTP 403 without IP whitelisting. `use_fixtures=True`
  mode reads from `data/phase2/fixtures/*.json` for offline dev — clearly labeled as fixtures via
  a `_fixture_note` key (which `process_raw_records` strips before building the `WeatherRecord`,
  unlike Phase 3A's approach — see §5).
- `src/ingestion/validators.py` — `validate_record()` does range-checks against
  `PLAUSIBLE_RANGES`, sets `verification_status` ("unverified"/"validated"/"flagged") and
  `confidence_score`. **Reused unmodified by ERA5 (Phase 2B) and Open-Meteo (Phase 2C) adapters**
  via an added optional `base_confidence` parameter (see §4's one disclosed exception).

### Phase 2B — ERA5+IMD fusion (COMPLETE, 20 tests)
- `src/adapters/era5_adapter.py` — ERA5 CSV → `WeatherRecord`. Documented unit conversions:
  Kelvin→Celsius, Pascal→hPa, metres→mm, wind components→speed+direction via `sqrt`/`atan2`.
  `ERA5_BASE_CONFIDENCE = 0.85` (stated assumption: model reanalysis, lower trust than IMD's
  direct-observation default of 0.9).
- `src/fusion/temporal_alignment.py` — `check_temporal_match(ts1, ts2, max_time_diff_minutes=60)`.
  Full timestamp parsing via `dateutil`, **never** date-only matching. Returns `TEMPORAL_MATCH` /
  `TEMPORAL_MISMATCH` / `TEMPORAL_UNKNOWN` (if either timestamp is missing/unparseable).
- `src/fusion/spatial_alignment.py` — `check_spatial_match(...)` via Haversine great-circle
  distance, `max_distance_km=25` default. Returns `SPATIAL_MATCH` / `SPATIAL_MISMATCH` /
  `SPATIAL_UNKNOWN`.
- `src/fusion/source_comparison.py` — `compare_variable(name, val_a, val_b)`: percent-difference
  thresholds (`<5%`→HIGH, `<15%`→MEDIUM, else→DISAGREEMENT) for temperature/pressure/wind_speed.
  **Rainfall is special-cased** to use an absolute-mm threshold instead, because percent-diff is
  meaningless near zero. `compare_records()` hardcodes the variable list:
  `["temperature", "pressure", "rainfall", "wind_speed"]` (humidity is NOT compared — ERA5 has no
  humidity field).
- `src/fusion/fusion_engine.py` — `fuse_pair(record_a, record_b, label_a="ERA5", label_b="IMD",
  ...)`. **Fully generic** — takes two arbitrary `WeatherRecord`s and two string labels; this
  genericness is exactly what let Phase 2C add a third source without modifying this file at all.
  Computes `source_agreement_confidence` (mean of per-variable agreement scores: HIGH=1.0,
  MEDIUM=0.6, DISAGREEMENT=0.2; -10% penalty if either match is "marginal", i.e. past 70% of its
  tolerance). On `SOURCE_DISAGREEMENT`, the fused value is explicitly `None` for that variable —
  never blindly averaged.
- **Known honest limitation:** the demo pairing (`scripts/run_phase2b_demo.py`) needed a
  **synthetic timestamp/coordinate override** for its "Part B" (agreement/disagreement
  demonstration), because the real IMD fixture is dated 2026 and real ERA5 data is 2024–2025 —
  they don't naturally overlap. This was clearly labeled and is exactly the gap Phase 2C closed.

### Phase 2C — ERA5+Open-Meteo real overlap (COMPLETE, 17 tests)
- **Real data, no synthetic shifting needed:** `data/raw/jabalpur_openmeteo_2024_2025.json` — a
  real response from `https://archive-api.open-meteo.com/v1/archive`
  (lat=23.25, lon=80.00 → snapped to grid point 23.233742, 80.0; 2024-01-01 to 2025-12-31, hourly,
  UTC, `wind_speed_unit=ms`). **This sandbox cannot reach `archive-api.open-meteo.com` directly**
  (not in the network allowlist) — the user fetched it locally and uploaded it. If a future session
  needs fresh/different Open-Meteo data, this same limitation will apply; give the user the exact
  `curl`/Python command and wait for the upload, exactly as done here.
- `src/adapters/openmeteo_adapter.py` maps `temperature_2m`→temperature, `relative_humidity_2m`→
  humidity, `surface_pressure`→pressure, `precipitation`→rainfall, `wind_speed_10m`→wind_speed
  (already m/s), `wind_gusts_10m`→stored in `raw_payload["wind_gust"]` (schema has no gust field,
  same treatment as ERA5's `fg10`). `wind_direction` is honestly `None` (not requested in the
  pull). `OPENMETEO_BASE_CONFIDENCE = 0.80`.
- **Critical, real, non-obvious finding: the pressure comparison is broken by a threshold artifact,
  not fixed.** The pull used `surface_pressure` (not `pressure_msl`). Jabalpur's real elevation is
  390m, so `surface_pressure` is ~35–46 hPa lower than ERA5's mean-sea-level pressure — real
  physics, not disagreement. **But** because pressure's baseline magnitude (~1000 hPa) is large, a
  46 hPa gap is only ~4.5% relative — under the existing 5% `SOURCE_AGREEMENT_HIGH` threshold. So
  **100% of pressure comparisons report HIGH agreement**, which is a **methodological artifact, not
  a real success** — it mirrors the exact reason rainfall already needed an absolute-mm threshold
  in Phase 2B, except pressure hasn't been fixed yet. This is documented in
  `src/adapters/openmeteo_adapter.py`'s docstring and asserted by
  `tests/test_phase2c_openmeteo.py::test_pressure_percent_threshold_masks_the_elevation_offset`.
  **Not yet fixed** — Phase 2B's `source_comparison.py` was deliberately left unmodified per
  instructions; fixing this (adding an absolute-hPa threshold for pressure, or re-pulling
  `pressure_msl`) is explicitly recommended for a future phase.
- Real stats over all 17,544 real overlapping hourly pairs (100% pairing rate, both
  `TEMPORAL_MATCH` at 0-minute diff and `SPATIAL_MATCH` at 1.808 km):
  - temperature: 55.4% HIGH, 40.9% MEDIUM, 3.7% DISAGREEMENT
  - pressure: 100% HIGH (see artifact above — not a real success)
  - rainfall: 94.1% HIGH, 5.2% MEDIUM, 0.7% DISAGREEMENT
  - wind_speed: 12.9% HIGH, 24.7% MEDIUM, **62.4% DISAGREEMENT** (real, reproducible — 10m wind
    speed is known to be inconsistent across reanalysis products)
  - Bonus wind_gust comparison (both sources have this outside the schema, compared directly via
    the existing generic `compare_variable()`): 16.4% HIGH, 31.2% MEDIUM, 52.4% DISAGREEMENT.
- **Scientific framing, must be preserved in any future work:** Open-Meteo's Historical Weather
  API is itself a **model/reanalysis blend** (`best_match`: ECMWF IFS + ERA5/ERA5-Land), **not
  independent ground truth**. ERA5+Open-Meteo agreement is a **cross-model comparison**, never to
  be described as "verified truth." IMD (Phase 2A) remains the only observational source in this
  architecture.
- Outputs in `data/phase2c/fused/`: `openmeteo_weather_records.{json,csv}`,
  `era5_openmeteo_comparison.csv`, `era5_openmeteo_fused_records.csv`, `phase2c_summary.json`.

### Phase 3A — Multi-source report ingestion (COMPLETE, 27 tests)
- **New, separate schema:** `src/schemas/weather_report.py` (`WeatherReport`), deliberately
  distinct from `WeatherRecord`. `WeatherRecord` = structured numeric met. observations;
  `WeatherReport` = unstructured/semi-structured human/third-party reports about weather events
  (free text, photos, social posts, citizen submissions), with its own trust model.
- Fields: `report_id`, `source_type`, `source_name`, `source_url`, `author_id_or_hash` (hashed,
  never raw), `timestamp`, `ingestion_timestamp`, `city`, `state`, `latitude`, `longitude`, `text`,
  `image_url`, `video_url`, `event_type` (normalized), `raw_event_type` (pre-normalization label),
  `verification_status`, `source_reliability`, `is_suspicious`, `is_duplicate`, `duplicate_hash`,
  `duplicate_group_id`, `metadata`, `raw_payload`.
- Controlled vocabularies: `source_type` ∈ {SOCIAL_MEDIA, CITIZEN_REPORT, PUBLIC_DATASET, WEBSITE,
  API}; `event_type` ∈ {RAINFALL, THUNDERSTORM, FLOODING, HEATWAVE, FOG, DUST_STORM, STRONG_WIND,
  OTHER}; `verification_status` ∈ {UNVERIFIED, VERIFIED, REJECTED, SUSPICIOUS} — **new reports are
  never auto-VERIFIED**.
- **No live social-media or citizen-app access exists.** `src/adapters/social_report_adapter.py`
  and `src/adapters/citizen_report_adapter.py` read from **clearly-labeled SYNTHETIC/DEMO**
  fixtures: `data/phase3/fixtures/social_weather_reports.json` (7 entries) and
  `citizen_weather_reports.json` (6 entries), covering 9 different Indian cities (not hardcoded to
  Jabalpur). Every fixture record's `_synthetic_note` is **preserved** inside the resulting
  `WeatherReport.raw_payload` (a deliberate, stronger departure from Phase 2A's IMD-fixture
  convention of stripping `_fixture_note`) — so the synthetic origin is always visible downstream,
  not just in a docstring.
- `src/adapters/social_report_adapter.py::infer_event_type_from_text()` — a transparent, ordered
  keyword-substring heuristic (NOT ML/NLP). `src/adapters/citizen_report_adapter.py::normalize_category()`
  — direct dropdown-category-string mapping.
- `src/ingestion/report_validators.py::validate_report()` — never silently discards. `REJECTED` for
  physically-impossible/structurally-unusable data (bad lat/lon, missing/unparseable timestamp,
  unknown source_type); `SUSPICIOUS` for unusual-but-possibly-real data (empty text + unrecognized
  category, no location at all); otherwise `UNVERIFIED`.
- `src/ingestion/report_normalizer.py::normalize_report()` — standardizes timestamp to UTC
  ISO-8601, collapses text whitespace, title-cases city/state, assigns baseline
  `source_reliability` from `DEFAULT_SOURCE_RELIABILITY` (a **stated, configurable assumption, not
  a scientific metric**): `API=0.85, PUBLIC_DATASET=0.75, WEBSITE=0.5, CITIZEN_REPORT=0.4,
  SOCIAL_MEDIA=0.3, UNKNOWN=0.2`.
- `src/ingestion/report_dedup.py::detect_duplicates()` — **deterministic baseline only, explicitly
  not ML/semantic**. `duplicate_hash = sha256(event_type | 30-min time bucket | 2-decimal-degree
  location bucket | exact normalized text)`. First-seen report per hash = original
  (`is_duplicate=False`); later ones with the same hash get `is_duplicate=True` and share
  `duplicate_group_id`.
- **Documented, deliberately-demonstrated limitation:** two independently-worded real reports of
  the *same* event (fixture includes exactly this case: "waterlogging near MG Road" vs. "MG Road is
  completely flooded", same place/time, different wording) are **not** caught as duplicates by this
  exact-text baseline. Proven by
  `test_near_duplicate_with_different_wording_is_not_caught_documented_limitation`. This is the
  explicit reason Phase 3B (semantic/ML similarity) is recommended next — not an oversight.
- Real demo run over the 13 synthetic fixture reports: 10 valid / 3 REJECTED (missing timestamp,
  invalid latitude >90, invalid longitude <-180), 2 exact duplicates correctly caught, 1 SUSPICIOUS
  (empty text + unrecognized category), 9 UNVERIFIED, 7 distinct event categories, 9 distinct
  city/state locations.
- Outputs in `data/phase3/processed/`: `all_weather_reports.{json,csv}`,
  `social_weather_reports_processed.json`, `citizen_weather_reports_processed.json`.

---

## 4. The One Disclosed Exception to "Never Modify Earlier Phases"

During Phase 2B, `src/ingestion/validators.py::validate_record()` had its range-check logic
identified as directly reusable by the new ERA5 adapter instead of being duplicated. **One
backward-compatible change was made**: an optional `base_confidence: float = 0.9` parameter was
added (default value preserves the exact original behavior). This was:
- Disclosed to the user **before** proceeding, and again in the final Phase 2B summary.
- Verified with a full Phase 2A test re-run before and after — all 7 tests passed identically.

This is the **only** modification to a completed phase's file across the entire project history.
Do not treat this as precedent for casual modifications — it was flagged as an exception
specifically because it avoided duplicating validated logic, and every future addition since
(Phase 2C, Phase 3A) has instead created new, separate files rather than touching existing ones
(e.g. `storage_fused_2c.py` instead of modifying `storage_fused.py`; `weather_report.py` instead of
extending `weather_record.py`).

---

## 5. Conventions to Preserve Going Forward

- **Dataclasses with `to_dict()` via `asdict()`.** Every schema (`WeatherRecord`, `WeatherReport`)
  follows this shape: typed fields, sensible `None` defaults (never guessed values), a
  `raw_payload: Optional[Dict]` for full traceability, a `to_dict()` method.
- **Adapters are pure functions:** `xxx_to_records()` / `xxx_fixture_to_reports()` load + map, then
  hand off to a `validate_*()` function — adapters do not validate inline.
- **Validators mutate and return the same object**, setting `verification_status` and
  `quality_flags`/similar, never raising exceptions for "normal" bad data (only for structurally
  malformed *files*, e.g. `openmeteo_adapter.py` raises `ValueError` if the JSON doesn't have the
  expected `hourly.time` shape at all — a different class of failure than a single bad record).
- **Every module docstring documents its thresholds/assumptions as "stated, not scientific."**
  Follow this pattern exactly for any new threshold you introduce.
- **Test files are runnable standalone** (`if __name__ == "__main__":` block with a manual
  pass/fail counter) as well as via pytest-style discovery — this project does not assume pytest is
  installed; keep this dual-compatibility.
- **New phases get their own storage module and output directory** (`data/phaseN/...`) rather than
  writing into a shared/previous directory or repurposing an earlier phase's CSV column names.
- **README is append-only**, one section per phase, each ending with a "Recommended next phase"
  subsection. Never delete or reword an earlier section.

---

## 6. Sandbox / Environment Constraints to Remember

- **No network access to `archive-api.open-meteo.com`** (or presumably other arbitrary external
  APIs) from this sandbox. If a task needs live data from a domain not already proven reachable,
  tell the user honestly and give them a copy-paste command to fetch it themselves, then wait for
  upload — do not guess or fabricate.
- **IMD's real API requires IP whitelisting** — confirmed via a real 401/403 test call in Phase 2A.
  This is a real, external constraint, not a sandbox limitation; fixtures remain the correct
  approach until/unless the user has whitelisting.
- File uploads from the user land in `/mnt/user-data/uploads/`; copy them into the actual project's
  `data/raw/` (or appropriate `dataN/...`) directory inside your working copy before running any
  adapter that reads from that path.
- When done, zip the **entire project directory** (not just new files) and deliver it via
  `present_files`, so the user always has one self-contained, complete, up-to-date copy.

---

## 7. Phase 3B — COMPLETE (27 → now 92 total tests passing)

Implemented exactly as recommended above: TF-IDF cosine semantic similarity (scoped to Phase 3A's
existing time+location buckets, not recomputed), TF-IDF+LogisticRegression event classification
(LOOCV-evaluated: 66.7% accuracy, 0.44 macro-F1, on 21 examples/8 classes — DEMO/BASELINE only,
explicitly labeled as such), and explainable rule-based risk scoring
(`LOW_RISK`/`MEDIUM_RISK`/`HIGH_RISK`/`UNVERIFIED`, never a fake/real verdict). New package:
`src/intelligence/{semantic_similarity,event_classifier,report_risk,report_intelligence,intelligence_storage}.py`.
`WeatherReport` was extended (backward-compatible, verified against Phase 3A's 27 tests before/after)
with new Optional fields (`semantic_similarity_score`, `predicted_event_category`, `risk_score`, etc.)
— `event_type` (Phase 3A's keyword-heuristic field) was never overwritten, only supplemented.

**Two real methodological findings, documented rather than hidden (same discipline as Phase 2C's
pressure-threshold artifact):**
1. Per-bucket TF-IDF (fit fresh on each 2-3-document bucket) produced unreliably low similarity
   scores — fixed by fitting IDF on the full batch corpus, then only *comparing* within buckets.
2. Even after that fix, TF-IDF is fundamentally lexical, not semantic — this project's own
   deliberately-constructed paraphrase pairs (different vocabulary, same real event) score only
   ~0.18-0.22 cosine similarity, landing as `POSSIBLE_RELATED_EVENT`, never confidently
   `SEMANTIC_DUPLICATE`. This is the concrete, evidenced reason Phase 3C should prioritize
   embedding-based similarity, once model-weight download access exists.

Fixtures were extended (Part G), not replaced: 8 new social + 4 new citizen entries, all carrying
the same `_synthetic_note` convention. One of my own fixture coordinates landed exactly on a
rounding boundary (17.3849 vs 17.385) during testing — a data bug I introduced and fixed myself,
not a "finding" worth documenting as a limitation.

Full test results at end of Phase 3B: **7 + 20 + 17 + 27 + 21 = 92 passed, 0 failed.**

## 8. Phase 3C — COMPLETE (92 → now 113 total tests passing)

Implemented exactly as recommended by Phase 3B's own §8 item 3: a new, entirely additive
**corroboration and verification layer**, `src/corroboration/` (`evidence_mapper.py`,
`temporal_evidence.py`, `spatial_evidence.py`, `report_correlator.py`, `verification_engine.py`,
`corroboration_storage.py`), that checks a Phase 3A/3B `WeatherReport`'s claimed event against real
weather evidence from Phase 2B (ERA5) and Phase 2C (Open-Meteo), plus the Phase 2A IMD fixture
where compatible.

**Architecture, reused rather than duplicated:**
- `temporal_evidence.py` calls Phase 2B's `fusion.temporal_alignment.check_temporal_match`
  unmodified for the actual match decision (only adds a bisect-indexed candidate search for
  efficiency over the real 17,544-record ERA5/Open-Meteo series).
- `spatial_evidence.py` calls Phase 2B's `fusion.spatial_alignment.check_spatial_match` unmodified,
  same 25 km default threshold used for ERA5↔IMD comparison.
- `report_correlator.py` loads the **already-generated** Phase 2B/2C JSON outputs
  (`data/phase2/fused/era5_weather_records.json`, `data/phase2c/fused/openmeteo_weather_records.json`)
  rather than re-running the ERA5/Open-Meteo adapters over all 17,544 rows again.
- `verification_engine.py` is the **only** module that assigns a `verification_status` or numeric
  score — every other module in the package only gathers/aligns raw evidence.

**Four verification statuses (never collapsed to binary true/false), per explicit instruction:**
`SUPPORTED` ("SUPPORTED BY AVAILABLE WEATHER EVIDENCE", never "report is true"), `CONFLICTING`
("CONFLICTING WITH AVAILABLE WEATHER EVIDENCE", never "report is fake"), `UNVERIFIED` (evidence
exists but is inconclusive, or sources disagree with each other and are NOT blindly averaged), and
`INSUFFICIENT_EVIDENCE` (missing timestamp/location, no matched record in any source, an unmapped
event category, or the required variable unavailable everywhere it was checked).

**Documented, stated evidence thresholds** (NOT scientifically calibrated against verified ground
truth — same discipline as Phase 2B's `PERCENT_THRESHOLDS`):
```
rainfall:    support >= 0.5 mm,   conflict <= 0.1 mm
temperature: support >= 40.0°C,   conflict <= 35.0°C   (heatwave)
wind_speed:  support >= 10.8 m/s, conflict <= 5.0 m/s   (strong wind / dust storm)
wind_gust:   support >= 15.0 m/s, conflict <= 7.0 m/s
humidity:    support >= 90.0%,    conflict <= 60.0%     (FOG — weak proxy only, explicitly flagged)
```
`evidence_support_score` is a transparent mean of per-source numeric verdict codes
(SUPPORTING=1.0, AMBIGUOUS=0.5, CONFLICTING=0.0), named that way and never `truth_probability`;
it is `None`, never invented, when no source has usable evidence.

**IMD is explicitly distinguished from a generic mismatch.** Per this project's own documented
constraint (Phase 2A's IMD fixture is dated ~2026, not genuine 2024–2025 station data), any report
with a real 2024/2025 timestamp gets the explicit reason `IMD_TEMPORAL_UNAVAILABLE` for the IMD
source, never a generic `NO_TEMPORAL_MATCH` — so "IMD cannot speak to this period" is never
confused with "IMD disagreed".

**Phase 3B integration:** `verify_report()` reads and preserves (never overwrites)
`predicted_event_category`, `event_classification_confidence`, `risk_label`, and `risk_score` from
Phase 3B in its output. Phase 3C's verdict lives in its own separate fields.

**One real, important, honest finding (same discipline as Phase 2C's pressure-threshold artifact
and Phase 3B's TF-IDF limitation):** run against `scripts/run_phase3c_demo.py`'s Part 1 (the real
25 Phase 3A/3B synthetic fixture reports vs. the real Phase 2B/2C evidence), **all 25 resolve to
`INSUFFICIENT_EVIDENCE`.** This is not a Phase 3C bug — Phase 3A's fixture reports are dated 2026
(fabricated posting times), while the real ERA5/Open-Meteo evidence only covers 2024-01-01 to
2025-12-31. There is currently **zero temporal overlap** between this project's existing synthetic
report fixtures and its real weather evidence. Part 2 of the same demo script uses 8 small,
clearly-labeled controlled edge-case fixtures timestamped inside the real 2024–2025 window to prove
the verification logic itself works correctly against real data (SUPPORTED, CONFLICTING, and a real
multi-source disagreement at 2024-01-05T15:00:00Z — ERA5 shows 0.80mm rainfall, Open-Meteo shows
0.0mm at the exact same real hour/location — correctly resolved to `UNVERIFIED`, not averaged away).

A second honest finding: **real 2024–2025 Jabalpur wind speed never reaches the 10.8 m/s
STRONG_WIND support threshold** (max observed: ERA5 ≈7.95 m/s, Open-Meteo ≈9.31 m/s). This
behavior is therefore proven in the test suite with a small, clearly-labeled synthetic
`EvidenceSource` fixture rather than real data — itself a useful data point about this project's
real wind climatology, documented rather than worked around by lowering the threshold to fit.

Combined demo totals across all 33 reports (25 real + 8 controlled edge cases):
`INSUFFICIENT_EVIDENCE: 28, SUPPORTED: 3, CONFLICTING: 1, UNVERIFIED: 1`. Outputs saved to
`data/phase3c/{corroborated_reports.json,corroborated_reports.csv,verification_summary.json}`.

Full test results this session: **7 + 20 + 17 + 27 + 21 + 21 = 113 passed, 0 failed.**

**Files created:** `src/corroboration/{__init__,evidence_mapper,temporal_evidence,spatial_evidence,
report_correlator,verification_engine,corroboration_storage}.py`, `scripts/run_phase3c_demo.py`,
`tests/test_phase3c_corroboration.py`, plus generated outputs in `data/phase3c/`.

**Files modified:** README.md only (append-only, new Phase 3C section) and this handoff document.
**No Phase 1/2A/2B/2C/3A/3B file was modified, renamed, or removed** — Phase 3C is entirely
additive and consumes earlier phases' outputs read-only.

## 9. Phase 4A — COMPLETE (113 → now 140 total tests passing)

New package `src/phase4/` (`weather_intelligence.py`, `intelligence_storage.py`) — a unified
`WeatherIntelligence` record per time/place combining: weather variables + `source_agreement_*`
(reused unmodified from Phase 2B/2C's `fuse_pair()`), `report_evidence` + `corroboration_status`
(reused unmodified from Phase 3C's `verify_report()` output, rolled up across the matched reports —
`SUPPORTED`+`CONFLICTING` present → `CONFLICTING`, never averaged), and a transparent
`overall_confidence` = mean of whichever of `source_agreement_confidence`/`evidence_support_score`
are not `None` (never fabricated when both are missing). `forecast`/`anomaly`/`alert` fields exist but
are always `None` — not implemented in 4A, per explicit instruction. Report-evidence selection reuses
Phase 2B's `check_temporal_match`/`check_spatial_match` unmodified — no new alignment logic was
written. **No Phase 1/2A/2B/2C/3A/3B/3C file was modified.**

`scripts/run_phase4a_demo.py` fuses real ERA5+Open-Meteo records (via `fuse_pair()`) at the 5 real
2024–2025 timestamps where Phase 3C's own demo produced a non-`INSUFFICIENT_EVIDENCE` verdict, and
attaches those real Phase 3C results: `SUPPORTED: 3, UNVERIFIED: 1, CONFLICTING: 1`. Outputs:
`data/phase4/weather_intelligence.{json,csv}`. **Known limitation:** the demo covers only those 5 real
timestamps, not the full 17,544-row series — see the script's own docstring/output.

`tests/test_phase4a_intelligence.py` — 27 tests (synthetic fixtures, offline): object creation,
single-source vs. fused variables, provenance, all four rollup outcomes, confidence calculation and
its "never fabricated" cases, unmatched fusion, serialization and storage round-trips.

Full test results: **113 + 27 = 140 passed, 0 failed.**

**Files created:** `src/phase4/{__init__,weather_intelligence,intelligence_storage}.py`,
`scripts/run_phase4a_demo.py`, `tests/test_phase4a_intelligence.py`, plus generated outputs in
`data/phase4/`. **Files modified:** README.md (append-only) and this handoff document only.

## 10. Recommended Next Step: Phase 4B (do NOT start this without explicit user instruction)

1. Extend `scripts/run_phase4a_demo.py`'s fusion loop across the full real 17,544-row ERA5/Open-Meteo
   series, not just the 5 timestamps with real Phase 3C report evidence.
2. Calibrate Phase 3C's evidence thresholds against real labeled outcomes, once any verified
   ground-truth event dataset exists.
3. Acquire a temporally-overlapping IMD source so `IMD_TEMPORAL_UNAVAILABLE` stops being the default.
4. Extend Phase 3A's report fixtures with dates inside the real 2024–2025 evidence window.
5. Embedding-based semantic similarity (Phase 3B's still-unaddressed recommendation).
6. The Phase 2C pressure-threshold artifact (§3, Phase 2C in this document) remains unaddressed.
7. Once Phase 4B is scoped, this is where `forecast`/`anomaly`/`alert` would actually be populated.

**Do not implement Phase 4B, 4C, or the pressure fix until the user explicitly asks for it.**

---

## 11. Quick Reference — Real Data Files Currently On Disk

| File | Real/Synthetic | Period | Records |
|---|---|---|---|
| `data/raw/jabalpur_weather_2024_2025.csv` | REAL (Copernicus CDS ERA5) | 2024-01-01–2025-12-31, hourly | 17,544 |
| `data/raw/jabalpur_openmeteo_2024_2025.json` | REAL (user-downloaded Open-Meteo) | 2024-01-01–2025-12-31, hourly | 17,544 |
| `data/phase2/fixtures/imd_current_wx_fixture.json` | SYNTHETIC/FIXTURE (IMD-shaped) | dated 2026 (fixture-creation time) | small |
| `data/phase2/fixtures/imd_aws_data_sample.json` | SYNTHETIC/FIXTURE | — | small |
| `data/phase3/fixtures/social_weather_reports.json` | SYNTHETIC/DEMO | dates 2026 (fabricated) | 15 (7 original + 8 added in Phase 3B) |
| `data/phase3/fixtures/citizen_weather_reports.json` | SYNTHETIC/DEMO | dates 2026 (fabricated) | 10 (6 original + 4 added in Phase 3B) |
| `models/phase3b/event_classifier_tfidf_logreg.pkl` | REAL trained model (on synthetic labels) | trained at runtime | ~24KB, DEMO/BASELINE only |

---

## 12. Phase 4B — COMPLETE (140 → now 154 total tests passing)

New package `src/phase4b/` (`feature_engineering.py`, `time_series_ml.py`, `model_persistence.py`,
`intelligence_integration.py`) — the advanced multi-horizon ML layer, additive on top of Phase 1's
baseline ML (`src/features/build_features.py`, `src/evaluation/time_series_eval.py`, both reused
unmodified). **No Phase 1/2A/2B/2C/3A/3B/3C/4A file was modified.**

Trained + evaluated on the real 17,544-row `data/processed/jabalpur_clean.csv`, chronologically split
(TRAIN→VAL→TEST, never shuffled): RandomForest + HistGradientBoosting for temperature (1h/3h/6h/12h/
24h ahead) and rain occurrence (same 5 horizons), leakage-safe features (causal lags/rolling stats,
documented and unit-tested), 20 saved model files under `models/phase4b/{temperature,rainfall}/` with
full metadata JSON alongside each. 1h temperature vs Phase 1's own recorded baseline (MAE 0.439):
Phase 4B RandomForest MAE 0.436 (materially the same), Phase 4B HistGradientBoosting MAE 0.364 (real
improvement, honestly caveated — feature set is wider than Phase 1's, not a strict ablation). Full
30-row model comparison table: `data/phase4b/model_comparison.{csv,json}`.

Phase 4A's `WeatherIntelligence.forecast` field (previously always `None`) is now populated for 3 of
Phase 4A's 5 real demo records (the 2 outside the leakage-safe lag-warm-up window are honestly
skipped, not fabricated) — `data/phase4b/weather_intelligence_with_forecast.json`.
`data/phase4/weather_intelligence.json` itself is untouched.

`tests/test_phase4b_ml.py` — 14 tests, small deterministic synthetic fixtures (never real-data
evaluation): feature generation, lag correctness, rolling correctness, chronological splitting,
leakage prevention, missing-value handling, temperature/rainfall model training, multi-horizon
support, metric calculation, model persistence + reload, reproducibility, Phase 4A compatibility.

**Full test results: 140 + 14 = 154 passed, 0 failed.**

**Files created:** `src/phase4b/{__init__,feature_engineering,time_series_ml,model_persistence,
intelligence_integration}.py`, `scripts/run_phase4b_demo.py`, `scripts/_phase4b_worker.py` (internal
per-horizon runner, used only because this sandbox's single CPU core made the full 10-combination
training run exceed one interactive execution window — same logic as `run_phase4b_demo.py`, no
different data/hyperparameters), `tests/test_phase4b_ml.py`, plus generated outputs in
`models/phase4b/` and `data/phase4b/`. **Files modified:** README.md (append-only) and this handoff
document only.

**Known limitations (see also README's Phase 4B section):** feature-set difference vs Phase 1 makes
the 1h baseline comparison honest-but-not-strictly-ablative; single grid point/single source; rainfall
F1 degrades at longer horizons (genuinely harder problem, not hidden); no hyperparameter search was
performed; the per-horizon-worker execution split is a sandbox artifact, not a Phase 4B design choice.

**Do not implement Phase 4C or Phase 4D until the user explicitly asks for it.**

## 13. Phase 4C — COMPLETE (154 → now 175 total tests passing)

New package `src/phase4c/` (`anomaly_features.py`, `anomaly_scoring.py`, `anomaly_detection.py`,
`anomaly_storage.py`) — weather anomaly detection + explainable anomaly analytics, additive on top of
Phase 2B/2C's adapters and Phase 4A's `WeatherIntelligence` (both reused unmodified). **No Phase
1/2A/2B/2C/3A/3B/3C/4A/4B file was modified.**

**What it does.** Detects statistically unusual observations in temperature, wind_speed, rainfall, and
pressure, per source, using causal rolling-window statistics (never looking at future data — same
`.shift(1).rolling(window)` convention Phase 4B's own feature engineering already established).
Temperature/wind/pressure use a rolling z-score; rainfall uses a rolling-percentile method instead,
because rainfall is zero-inflated and an ordinary z-score would flag routine light rain as "extreme."
Every finding is classified as the literal string `STATISTICAL_ANOMALY` (or `NORMAL`) — **never**
`DISASTER`/`EMERGENCY`/`CYCLONE`/`FLOOD`/`HEATWAVE`/`TORNADO`, per the explicit spec requirement that
a statistical anomaly is not automatically any of those things.

**Real-data run** (`scripts/run_phase4c_demo.py`, real ERA5 + Open-Meteo, Jabalpur, 2024–2025, 17,544
rows per source, loaded via the existing unmodified adapters): 140,352 total observations analyzed,
1,309 statistical anomalies (0.93% rate) — temperature 28, wind_speed 418, pressure 170, rainfall 693;
ERA5 677 / Open-Meteo 632; severity LOW 865 / MEDIUM 134 / HIGH 61 / CRITICAL 249; 1,344
insufficient-history observations (the first 168–720 rows of each source/variable, as designed); 0
missing/invalid/zero-variance in the real data. Rainfall anomalies concentrate in the monsoon season
(647/693, ~93%) — checked manually as a scientific sanity check before write-up, per the spec's
"scientific validation" requirement, and matches real-world seasonal expectation rather than looking
like an artifact.

**Pressure caveat, explicitly carried forward.** Phase 2C documented that ERA5's pressure field is
mean-sea-level pressure while Open-Meteo's is surface pressure, ~35–46 hPa apart at Jabalpur's
elevation. Phase 4C's detectors never compare sources to each other (every rolling baseline is built
purely from one source's own past values), so this cannot itself produce a false anomaly here — this
is directly asserted by
`test_pressure_caveat_not_triggered_by_cross_source_definition_mismatch` and restated in every
pressure `AnomalyRecord.explanation`.

**Storage note.** `data/phase4c/anomalies.json`/`.csv` store only the actual `STATISTICAL_ANOMALY`
findings (~1,600 rows), not all ~140k scored observations — an earlier draft persisted everything and
produced a 164MB JSON file of near-zero information content; the full breakdown by status
(EVALUATED/INSUFFICIENT_HISTORY/etc.) lives in `data/phase4c/anomaly_summary.json` instead, computed
from the full in-memory run.

**Phase 4A integration (additive).** `attach_anomalies_to_intelligence()` fills the pre-existing,
previously-`None` `WeatherIntelligence.anomaly` field, reusing Phase 4A's own
`check_temporal_match`/`check_spatial_match` alignment (no new matching logic) — `None` when nothing
aligns, never fabricated. Output: `data/phase4c/weather_intelligence_with_anomalies.json` (a new file;
`data/phase4/weather_intelligence.json` itself is untouched).

**Phase 4B integration (additive, context only).** `attach_anomaly_context_to_forecast()` adds an
`observed_anomaly_context` list to a *copy* of each Phase 4B forecast record — never edits the
predicted value, never labels a forecast as an observation. Output:
`data/phase4c/forecast_with_anomaly_context.json` (`data/phase4b/weather_intelligence_with_forecast.json`
itself is untouched).

`tests/test_phase4c_anomaly_detection.py` — 21 tests, small deterministic synthetic fixtures: normal
values, obvious temperature/wind/rainfall/pressure anomalies, the pressure non-trigger, missing
values, insufficient history, zero variance, boundary threshold, duplicate-timestamp dedup, unsorted
input, reproducibility, source separation, severity scaling, explanation generation, storage
round-trip, Phase 4A/4B integration, and a real-data smoke test (skips gracefully if the real data
file isn't present).

**Full test results: 154 + 21 = 175 passed, 0 failed.** (Two of the 21 new tests' own synthetic
fixtures initially had a bug — near-zero-variance baselines that made a "mild" deviation statistically
huge, and a rainfall pattern too sparse for the rolling p95 to stabilize — both were fixed in the test
fixtures themselves, not in the detection logic, before the suite went green.)

**Files created:** `src/phase4c/{__init__,anomaly_features,anomaly_scoring,anomaly_detection,
anomaly_storage}.py`, `scripts/run_phase4c_demo.py`, `tests/test_phase4c_anomaly_detection.py`, plus
generated outputs in `data/phase4c/`. **Files modified:** README.md (append-only) and this handoff
document only.

**Known limitations (see also README's Phase 4C section):** window sizes and thresholds are documented
standard-convention defaults, not fitted against any labeled ground-truth anomaly set (none exists in
this project); the rolling-window methods don't explicitly model seasonality within the window, so a
window spanning a rapid seasonal transition could under-flag a genuine anomaly right at that boundary;
only ERA5 and Open-Meteo were run through the real-data demo (IMD/citizen-report data from earlier
phases doesn't carry the same dense hourly series a rolling-window method needs).

**Do not implement Phase 4D until the user explicitly asks for it.**

---

*End of handoff document. When resuming this project in a new session, treat the actual files in
the uploaded zip as authoritative over anything summarized here — this document may lag behind
the true state if further work happened after it was written.*
