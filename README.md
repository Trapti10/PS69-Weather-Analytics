# PS69 – Weather Analytics (SIH 2026)

## Problem framing

The real problem behind PS69 is **weather-data fragmentation**: weather information is scattered
across IMD, ISRO/MOSDAC, weather stations, radar, satellites, and historical/reanalysis datasets —
each with different formats, resolutions, and update frequencies. The goal is an **intelligent
weather analytics and data-fusion platform**, not just a single prediction model.

## Phase 1 (this repository)

Phase 1 proves out the core methodology on a single, clean historical source before scaling to full
multi-source fusion:

- **Data:** ERA5 reanalysis, Jabalpur, hourly, 2024–2025 (`data/raw/jabalpur_weather_2024_2025.csv` —
  note: this is a Copernicus CDS zip archive saved with a `.csv` extension; handled automatically)
- **Pipeline:** inspection → data-quality checks → cleaning/unit conversion → EDA → feature engineering
  → ML-problem selection (evidence-based) → baseline modeling → time-series-aware evaluation
- **Selected problems:** short-term temperature forecasting (primary) and rain occurrence
  classification (secondary) — see `reports/findings.md` for why, with evidence from the data itself

Full results, evidence, and limitations: **[`reports/findings.md`](reports/findings.md)**

## Project structure

```
PS69-Weather-Analytics/
├── data/
│   ├── raw/                    # Phase 1: original ERA5 download
│   ├── processed/              # Phase 1: cleaned data, engineered features, trained models
│   └── phase2/
│       ├── fixtures/           # Phase 2A: offline IMD test fixtures (see Phase 2A section)
│       ├── raw/                # Phase 2A: raw IMD API pulls (audit trail)
│       ├── processed/          # Phase 2A: standardized IMD WeatherRecords
│       └── fused/              # Phase 2B: ERA5 WeatherRecords + comparison + fused output
├── notebooks/                  # Phase 1: 01-06, unchanged since Phase 1
├── src/
│   ├── data/, features/, evaluation/, models/   # Phase 1 modules, unchanged
│   ├── schemas/weather_record.py                # shared WeatherRecord schema (Phase 2A+2B)
│   ├── ingestion/               # Phase 2A: IMD client, validators, storage
│   ├── adapters/era5_adapter.py # Phase 2B: ERA5 CSV -> WeatherRecord
│   └── fusion/                  # Phase 2B: temporal/spatial alignment, comparison, fusion engine
├── scripts/
│   ├── run_imd_ingestion.py    # Phase 2A entry point
│   └── run_phase2b_demo.py     # Phase 2B entry point
├── tests/
│   ├── test_phase2_ingestion.py  # Phase 2A tests
│   └── test_phase2b_fusion.py    # Phase 2B tests
├── reports/findings.md
├── download_weather.py          # Phase 1: cdsapi script used to pull the ERA5 CSV
├── requirements.txt
└── README.md
```

## Running it

```bash
pip install -r requirements.txt
jupyter notebook notebooks/01_data_exploration.ipynb
```

Run the notebooks in order (01 → 06) — each one saves outputs that the next one reads from
`data/processed/`.

## Key methodological rules followed throughout

- **No random shuffling before splitting.** All train/val/test splits are strictly chronological.
- **No data leakage.** All lag/rolling features use only past values (`.shift()`-based).
- **No fabricated results.** Every number in `reports/findings.md` comes from actually executing the
  notebooks against the real dataset — no estimated or placeholder metrics.
- **Honest scope.** Phase 1 does not claim to solve PS69 by itself — it is the single-source baseline
  the full multi-source fusion architecture builds on (see `reports/findings.md` §6–7).

## Target architecture (beyond Phase 1)

```
ERA5 + IMD + MOSDAC + weather stations + satellite/radar
        ↓ Data ingestion
        ↓ Data standardization
        ↓ Data quality checks
        ↓ Data fusion
        ↓ Analytics / ML
        ↓ Risk intelligence
        ↓ GIS dashboard / alerts
```

## Phase 2A — IMD Ingestion (completed)

Ingests IMD's documented `current_wx` / `aws_data` endpoints, validates and standardizes them into
the shared `WeatherRecord` schema, and stores JSON/CSV output. The live IMD API returned a real,
verified `403` (IP whitelisting required) — see `src/ingestion/imd_client.py` for the honest
handling of that, and `data/phase2/fixtures/` for the offline fixtures used for development and
testing until whitelisting is available. Run: `python scripts/run_imd_ingestion.py --mode fixtures`.

## Phase 2B — Multi-Source Integration & Data Fusion

**1. Why multiple sources are needed.** IMD ground observations and ERA5 reanalysis each have
different strengths and blind spots — ERA5 is a modeled, spatially-continuous reanalysis; IMD is a
direct but sparse, station-based observation. Neither alone is "ground truth"; comparing them is how
the platform will eventually build trustworthy, traceable weather intelligence instead of quietly
picking one source and hoping it's right.

**2. How ERA5 and IMD are normalized.** Both are converted into the exact same `WeatherRecord`
dataclass (`src/schemas/weather_record.py`) — the same one Phase 2A already used for IMD. ERA5's
adapter (`src/adapters/era5_adapter.py`) documents every unit conversion explicitly: temperature
Kelvin→Celsius, pressure Pascal→hPa, precipitation metres→mm, wind components→speed+direction. No
unit is assumed or silently guessed.

**3. How temporal alignment works** (`src/fusion/temporal_alignment.py`). Full timestamps are parsed
and compared — never date-only matching. `time_difference_minutes` is computed and compared against
a configurable `max_time_diff_minutes` (default 60, since ERA5 is hourly). Missing/unparseable
timestamps are explicitly `TEMPORAL_UNKNOWN`, never assumed to match.

**4. How spatial alignment works** (`src/fusion/spatial_alignment.py`). Haversine great-circle
distance between the two sources' coordinates, compared against a configurable `max_distance_km`
(default 25 km — a stated assumption reflecting IMD's sparse station network relative to ERA5's
grid, not a scientific constant). Missing coordinates are `SPATIAL_UNKNOWN`, never assumed to match
because two records happen to share a city name.

**5. How source comparison works** (`src/fusion/source_comparison.py`). For temperature, pressure,
and wind speed: percentage difference against thresholds (< 5% = HIGH agreement, < 15% = MEDIUM,
else DISAGREEMENT). Rainfall uses an absolute-mm threshold instead, since percentage difference is
meaningless near zero (0mm vs 0.2mm is not a real disagreement). Every comparison preserves both raw
source values — nothing is overwritten.

**6. How disagreements are detected and handled.** A `SOURCE_DISAGREEMENT` flag on a variable means
that variable is **not averaged** — the fused value for it is explicitly `null`, and both raw values
remain visible in the output. This was verified with real data: our own ERA5 (Jan, ~22°C) vs. IMD
fixture (dated in August, ~29°C) values genuinely disagree once time-aligned for demonstration,
correctly triggering `SOURCE_DISAGREEMENT` rather than being blindly averaged into a meaningless
25.6°C.

**7. How confidence is calculated** (`src/fusion/fusion_engine.py`), called `source_agreement_confidence`
— explicitly **not** a claim of real-world meteorological certainty:
   1. Fusion is only attempted if both temporal AND spatial checks pass (`MATCHED`); otherwise no
      confidence score is produced at all.
   2. Each compared variable's agreement flag maps to a number: HIGH→1.0, MEDIUM→0.6, DISAGREEMENT→0.2.
   3. The record's confidence is the mean of those per-variable scores.
   4. If either match is "marginal" (past 70% of its allowed tolerance), confidence is reduced by a
      further 10% — a match just inside the window is less trustworthy than one comfortably inside it.

**8. Why we preserve source-level observations.** Every fusion result keeps both sources' full
`WeatherRecord` objects (`result["sources"]["ERA5"]`, `result["sources"]["IMD"]`) plus the per-variable
comparison — so any fused value can always be traced back to what produced it and why. This is the
traceability principle the whole platform is built around, not just a Phase 2B convenience.

**9. Scaling beyond ERA5+IMD.** `fuse_pair()` takes two generic `WeatherRecord` objects and two
source-name labels — it has no ERA5/IMD-specific logic baked in. Adding MOSDAC, a citizen report, or
a third weather-station feed later means writing one more adapter that emits `WeatherRecord` objects
and calling the same alignment/comparison/fusion functions pairwise; the alignment, comparison, and
fusion modules do not need to change.

### Honesty note on the Phase 2B demonstration

Real ERA5 data covers 2024–2025; the real IMD fixture (from Phase 2A) is dated at fixture-creation
time (2026), so the two genuinely don't share a natural time window. `scripts/run_phase2b_demo.py`
shows this honestly in three parts: (A) the real, unmodified pairing — correctly reports
`TEMPORAL_MISMATCH`/`SPATIAL_UNKNOWN`, nothing hidden; (B1/B2) a clearly-labeled **synthetic pairing**
where only the IMD record's timestamp/coordinates are overridden to align with an ERA5 timestamp for
illustration — the underlying measurement values are the real fixture values, never fabricated. This
is explicitly documented in the script's own docstring and printed output, not glossed over.

### Running Phase 2B

```bash
pip install -r requirements.txt   # adds python-dateutil for timestamp parsing
python scripts/run_phase2b_demo.py
python tests/test_phase2b_fusion.py    # 20 tests, all passing
python tests/test_phase2_ingestion.py  # Phase 2A's 7 tests, still passing unchanged
```

Outputs land in `data/phase2/fused/`: `era5_weather_records.{json,csv}`, `source_comparison.csv`,
`fused_weather_records.{json,csv}` — Phase 2A's `data/phase2/processed/` outputs are untouched.

### National-scale design (not yet implemented, but not blocked either)

Nothing in `src/fusion/` or `src/adapters/era5_adapter.py` hardcodes Jabalpur — every location comes
from the `WeatherRecord.latitude/longitude` fields on the data itself. Scaling up is a data-loading
and orchestration change, not a fusion-logic rewrite:

- **1 → 10 locations:** loop `fuse_pair()` over a list of (ERA5 record, IMD record) pairs per city —
  no code change needed in `fusion/`, only in whatever script gathers the pairs
- **10 → 100 locations:** the flat-file storage in `src/fusion/storage_fused.py` should become a real
  database (PostgreSQL/PostGIS, consistent with the architecture frozen earlier) so comparisons can be
  queried by location/time instead of re-reading whole CSV/JSON files
- **100 → thousands / nationwide:** this is where scheduled ingestion, a proper spatial index (PostGIS),
  and batch/parallel processing genuinely become necessary — but that is explicitly **not** implemented
  in Phase 2B, per the instruction not to introduce Kafka/Spark/distributed processing yet. The fusion
  math itself does not need to change; only how much data flows through it and how it's stored/queried.

## Phase 2C — Real Overlapping Multi-Source Validation (Open-Meteo)

**1. Goal.** Add a third real source (Open-Meteo Historical Weather API) with genuine overlapping
time coverage with ERA5, so the fusion demo no longer needs the synthetic timestamp alignment that
Phase 2B's IMD pairing required (real ERA5 2024–25 vs. a real IMD fixture dated 2026).

**2. Data.** `data/raw/jabalpur_openmeteo_2024_2025.json` — a real, unmodified response from
`https://archive-api.open-meteo.com/v1/archive` for latitude 23.25, longitude 80.00 (Open-Meteo snapped
this to its nearest model grid point: 23.233742, 80.0), 2024-01-01 to 2025-12-31, hourly,
`timezone=UTC`, `wind_speed_unit=ms`. This sandbox's network allowlist does not include
`archive-api.open-meteo.com`, so the user fetched it locally with the verified `curl`/Python command
and uploaded the real file back — no synthetic or fabricated data was substituted at any point.

**3. Critical scientific limitation — stated plainly, not glossed over.** Open-Meteo's Historical
Weather API is itself **model/reanalysis output** (a `best_match` blend of ECMWF IFS and
ERA5/ERA5-Land), **not an independent ground observation**. Phase 2C is therefore a **cross-model
comparison**, not a model-vs-truth validation. IMD (Phase 2A) remains the only observational source
in this architecture. Nowhere in Phase 2C's code or output is ERA5+Open-Meteo agreement described as
"verified truth."

**4. Adapter.** `src/adapters/openmeteo_adapter.py` maps the real JSON's hourly arrays into the same
shared `WeatherRecord` schema Phase 2A (IMD) and Phase 2B (ERA5) already use — reusing
`ingestion/validators.py::validate_record` unchanged, exactly like the ERA5 adapter does. Mapping:
`temperature_2m`→temperature, `relative_humidity_2m`→humidity, `surface_pressure`→pressure,
`precipitation`→rainfall, `wind_speed_10m`→wind_speed (already m/s per the request),
`wind_gusts_10m`→stored in `raw_payload["wind_gust"]` (schema has no gust field, same treatment as
ERA5's `fg10`). `wind_direction` is honestly `None` — direction was not requested in this pull.

**5. Pressure caveat — an important, real, non-obvious finding.** The request used Open-Meteo's
`surface_pressure`, not `pressure_msl` (mean-sea-level pressure). ERA5's pipeline uses `msl`. Jabalpur's
station elevation in the real response is 390m, so `surface_pressure` is systematically **~35–46 hPa
lower** than ERA5's MSL value — real physics (altitude), not a genuine weather disagreement.

**6. Methodological finding: the existing percent-based agreement thresholds mask this offset.**
Because pressure's baseline magnitude (~1000 hPa) is large, a real 46 hPa gap is only ~4.5% relative
difference — under Phase 2B's existing 5% `SOURCE_AGREEMENT_HIGH` threshold (`fusion/source_comparison.py`,
unmodified). Every pressure comparison in the real run reports `SOURCE_AGREEMENT_HIGH` despite the
known elevation offset. This mirrors why rainfall already needed an absolute-mm threshold instead of a
percentage one — pressure has the same problem but is not yet special-cased. This is documented here
and asserted by `tests/test_phase2c_openmeteo.py::test_pressure_percent_threshold_masks_the_elevation_offset`
rather than silently patched, per the instruction not to modify Phase 2B files in this phase.

**7. Real overlap — no synthetic timestamp shifting.** Both real files cover the identical 17,544-hour
period. Pairing uses each record's actual parsed timestamp (via the unmodified
`fusion/temporal_alignment.py::check_temporal_match`) — never date-only matching. Result: all 17,544
ERA5 records find a real Open-Meteo record at the exact same UTC hour, and all 17,544 pairs pass both
`TEMPORAL_MATCH` (0-minute difference) and `SPATIAL_MATCH` (1.808 km grid-point distance, real
Haversine, well inside the existing 25km threshold) — genuinely, without any timestamp override.

**8. Real agreement/disagreement statistics** (see `scripts/run_phase2c_demo.py` output and
`data/phase2c/fused/phase2c_summary.json` for exact numbers): temperature agrees at HIGH/MEDIUM levels
for the large majority of hours with a small real disagreement tail; rainfall agrees highly the large
majority of the time; wind_speed disagrees far more often than it agrees (a genuine, reproducible
finding — 10-m wind speed is well known to be one of the least consistent variables across reanalysis
products, being highly sensitive to model resolution and boundary-layer parameterization); pressure is
HIGH across the board for the reason explained in point 6.

**9. Bonus comparison.** Both sources genuinely provide wind gust (ERA5's `fg10`, Open-Meteo's
`wind_gusts_10m`) outside the shared schema — Phase 2C compares these directly via the existing generic
`compare_variable()` (reused, not duplicated) as an extra, clearly-labeled bonus statistic.

**10. Files added:** `src/adapters/openmeteo_adapter.py`, `src/fusion/storage_fused_2c.py` (new,
separate from Phase 2B's `storage_fused.py` so its ERA5/IMD-specific column names are never
repurposed), `scripts/run_phase2c_demo.py`, `tests/test_phase2c_openmeteo.py`. **Files modified:**
only this README (append-only) — Phase 1, Phase 2A, and Phase 2B source/data files are untouched.

### Running Phase 2C

```bash
python scripts/run_phase2c_demo.py
python tests/test_phase2c_openmeteo.py   # 17 tests, all passing
python tests/test_phase2b_fusion.py      # Phase 2B's 20 tests, still passing unchanged
python tests/test_phase2_ingestion.py    # Phase 2A's 7 tests, still passing unchanged
```

Outputs land in `data/phase2c/fused/` (new directory): `openmeteo_weather_records.{json,csv}`,
`era5_openmeteo_comparison.csv`, `era5_openmeteo_fused_records.csv`, `phase2c_summary.json` — Phase
2A's and Phase 2B's output directories are untouched.

### Recommended Phase 3

1. Re-pull Open-Meteo with `pressure_msl` instead of (or alongside) `surface_pressure`, to remove the
   elevation confound identified in point 6, and consider an absolute-hPa agreement threshold for
   pressure (mirroring rainfall's existing absolute-mm special case).
2. Investigate the wind_speed disagreement rate with real per-hour diagnostics (time-of-day, season,
   monsoon vs. non-monsoon) rather than a single aggregate percentage.
3. Bring IMD (Phase 2A) into a real three-way overlap once real (non-fixture) IMD data with a
   2024–2025-overlapping timestamp is available, so the platform can finally compare model outputs
   against an actual ground observation, not just against each other.
4. Move fused storage to PostgreSQL/PostGIS once a genuine multi-location, multi-source dataset exists
   (consistent with the scaling discussion already documented in the Phase 2B section above).

## Phase 3A — Multi-Source Weather Report / Citizen Report Ingestion Layer

**1. Goal.** PS69 requires the platform to collect weather-related information from heterogeneous
internet-based sources: social media, public datasets, websites, APIs, and citizen reports. Phase 3A
builds the source-agnostic ingestion architecture for this — schema, adapters, validation,
normalization, and deterministic deduplication — using clearly-labeled synthetic fixtures for social
media and citizen reports, since no live platform access exists yet.

**2. Honesty note — read before anything else.** This phase does **not** have live access to
Twitter/X, Instagram, Facebook, or any real citizen-reporting backend. `src/adapters/social_report_adapter.py`
and `src/adapters/citizen_report_adapter.py` read from clearly-labeled SYNTHETIC/DEMO fixtures
(`data/phase3/fixtures/*.json`). Every fixture record carries a `_synthetic_note` field that is
**preserved** (not stripped) inside the resulting `WeatherReport.raw_payload`, so any downstream
consumer can always see, from the record itself, that it originated from synthetic data — this is a
deliberate departure from Phase 2A's IMD-fixture convention (which strips its `_fixture_note`),
chosen here because report data is closer to "real-looking" free text and needs a stronger, permanent
label. No real people, accounts, GPS traces, photos, or videos are represented anywhere in this phase.

**3. New schema — `src/schemas/weather_report.py` (`WeatherReport`).** Deliberately **separate** from
`WeatherRecord`: `WeatherRecord` represents structured meteorological *observations* (ERA5, IMD,
Open-Meteo — numeric, known-unit sensor/model values); `WeatherReport` represents unstructured/semi-
structured human or third-party *reports* about weather *events* (free text, photos, social posts,
citizen submissions) with a different trust model (unverified by default, deduplication-prone).
Fields: `report_id`, `source_type`, `source_name`, `source_url`, `author_id_or_hash` (hashed, never a
raw handle/name), `timestamp`, `ingestion_timestamp`, `city`, `state`, `latitude`, `longitude`, `text`,
`image_url`, `video_url`, `event_type` (normalized), `raw_event_type` (original label before
normalization), `verification_status`, `source_reliability`, `is_suspicious`, `is_duplicate`,
`duplicate_hash`, `duplicate_group_id`, `metadata`, `raw_payload`. `WeatherRecord` itself is untouched.

**4. Controlled vocabularies.** `source_type` ∈ {SOCIAL_MEDIA, CITIZEN_REPORT, PUBLIC_DATASET, WEBSITE,
API}. `event_type` ∈ {RAINFALL, THUNDERSTORM, FLOODING, HEATWAVE, FOG, DUST_STORM, STRONG_WIND, OTHER}.
`verification_status` ∈ {UNVERIFIED, VERIFIED, REJECTED, SUSPICIOUS} — **new reports are never
auto-VERIFIED** (enforced by `report_validators.py` and asserted by
`test_new_reports_never_auto_verified`). The schema is not hardcoded to any city — fixtures cover nine
different Indian cities/states to prove this (see point 8).

**5. Pipeline (matches the required architecture exactly).**
```
Raw source (synthetic fixture)
   -> Source adapter (social_report_adapter.py / citizen_report_adapter.py)
   -> WeatherReport
   -> Validation      (src/ingestion/report_validators.py)
   -> Normalization   (src/ingestion/report_normalizer.py)
   -> Deduplication prep (src/ingestion/report_dedup.py)
   -> Processed reports (src/ingestion/report_storage.py -> data/phase3/processed/)
```

**6. Validation (`report_validators.py`) — never silently discards.** Checks: known `source_type`,
parseable/present `timestamp`, latitude ∈ [-90, 90], longitude ∈ [-180, 180], some location info present
(city/state or lat/lon), known `event_type`, minimum/maximum text length. Physically-impossible or
structurally unusable records (bad lat/lon, missing/unparseable timestamp, unknown source type) are
marked `REJECTED`; unusual-but-possibly-real records (empty text + unrecognized category, no location
at all) are marked `SUSPICIOUS`. **Every record is returned and stored regardless of outcome** — nothing
is dropped from the pipeline, per the explicit instruction not to silently discard data.

**7. Normalization (`report_normalizer.py`).** Reformats `timestamp` to a consistent UTC ISO-8601
string, collapses/strips `text` whitespace, title-cases `city`/`state`, and assigns a baseline
`source_reliability` score (if not already set) from `DEFAULT_SOURCE_RELIABILITY` — a **stated,
configurable assumption, not a scientifically validated trust metric**:
`API=0.85, PUBLIC_DATASET=0.75, WEBSITE=0.5, CITIZEN_REPORT=0.4, SOCIAL_MEDIA=0.3, UNKNOWN=0.2`.

**8. Fixtures — 13 synthetic reports across 9 Indian cities.** `social_weather_reports.json` (7
entries: Jabalpur ×3 including one exact duplicate and one differently-worded near-duplicate, Delhi,
Bhopal, Jaipur with a missing timestamp, Chennai with an impossible latitude). `citizen_weather_reports.json`
(6 entries: Jabalpur ×2 exact duplicate, Nagpur, Patna with an impossible longitude, Lucknow with empty
text + unknown category, Kolkata). Deliberately not hardcoded to Jabalpur, and deliberately includes
malformed entries so validation has real cases to catch.

**9. Deduplication (`report_dedup.py`) — deterministic baseline, explicitly not ML/semantic yet.**
`duplicate_hash = sha256(event_type | 30-minute time bucket | 2-decimal-degree location bucket |
exact normalized text)`. The first report seen for a given hash in a batch is the "original"
(`is_duplicate=False`); later reports sharing that hash get `is_duplicate=True` and the same
`duplicate_group_id`. **Documented, demonstrated limitation:** two independently-worded real reports
of the *same* event (e.g. "waterlogging near MG Road" vs. "MG Road is completely flooded") are **not**
caught by this exact-text baseline — proven by the fixtures and by
`test_near_duplicate_with_different_wording_is_not_caught_documented_limitation`. This gap is exactly
why Phase 3B (semantic/ML similarity) is the recommended next step, not an oversight here.

**10. Files added:** `src/schemas/weather_report.py`, `src/ingestion/report_validators.py`,
`src/ingestion/report_normalizer.py`, `src/ingestion/report_dedup.py`, `src/ingestion/report_storage.py`,
`src/adapters/social_report_adapter.py`, `src/adapters/citizen_report_adapter.py`,
`data/phase3/fixtures/{social_weather_reports.json,citizen_weather_reports.json}`,
`scripts/run_phase3a_demo.py`, `tests/test_phase3a_reports.py`. **Files modified:** only this README
(append-only). `WeatherRecord` and every Phase 1/2A/2B/2C file are untouched.

### Running Phase 3A

```bash
python scripts/run_phase3a_demo.py
python tests/test_phase3a_reports.py     # 27 tests, all passing
python tests/test_phase2c_openmeteo.py   # Phase 2C's 17 tests, still passing unchanged
python tests/test_phase2b_fusion.py      # Phase 2B's 20 tests, still passing unchanged
python tests/test_phase2_ingestion.py    # Phase 2A's 7 tests, still passing unchanged
```

Outputs land in `data/phase3/processed/` (new directory): `all_weather_reports.{json,csv}`,
`social_weather_reports_processed.json`, `citizen_weather_reports_processed.json` — no earlier
phase's output directory is touched.

### Recommended Phase 3B

Add a semantic/ML similarity layer on top of (not replacing) Phase 3A's deterministic dedup baseline,
specifically to catch the documented gap in point 9 — differently-worded reports of the same real
event. A lightweight embedding-similarity or entailment model, applied only within an already-matched
time+location bucket (reusing Phase 3A's bucketing, not recomputing it), would be a natural next step,
along with a real (rule-based-to-ML) event-type classifier to replace `infer_event_type_from_text`'s
keyword heuristic.

## Phase 3B — Semantic & ML Intelligence Layer

**1. Objective.** Close the gap Phase 3A deliberately demonstrated and left open: exact-hash
deduplication cannot recognize two differently-worded reports of the same real event. Add a semantic
similarity layer, a real (ML) event classifier alongside Phase 3A's keyword heuristic, and an
explainable risk/suspicion score — without touching any Phase 1/2A/2B/2C/3A file's behavior.

**2. Architecture.**
```
Phase 3A output (validated, normalized, exact-deduplicated WeatherReports)
        ↓
Semantic similarity (TF-IDF cosine, within Phase 3A's existing time+location buckets)
        ↓
Event classification (TF-IDF + Logistic Regression, LOOCV-evaluated)
        ↓
Risk / suspicion scoring (explainable, rule-based)
        ↓
Intelligent WeatherReport (same object, new fields populated) → data/phase3b/
```
New package: `src/intelligence/{semantic_similarity,event_classifier,report_risk,report_intelligence}.py`
+ `intelligence_storage.py`. `WeatherReport` was extended (not replaced) with new `Optional`/defaulted
fields appended at the end of the dataclass — verified backward-compatible against Phase 3A's 27 tests
before and after.

**3. Semantic similarity method.** TF-IDF (unigrams+bigrams, English stop words removed) + cosine
similarity. **Library choice was verified against the actual environment, not assumed:** scikit-learn
is already a dependency and works fully offline; `sentence-transformers` is not installed, and even if
installed, downloading real pretrained weights needs `huggingface.co`, which this sandbox cannot reach
(same class of constraint as Phase 2C's Open-Meteo access). TF-IDF+cosine is therefore the honest,
actually-runnable choice — deterministic, explainable, zero downloads.

Comparisons are scoped to the **same time+location bucket that Phase 3A's `report_dedup.py` already
computes** (`_time_bucket`/`_location_bucket`, imported directly, not recomputed) — a Delhi report's
text is never compared to a Chennai report's. Reports already `is_duplicate=True` from Phase 3A's
exact-hash dedup are labeled `EXACT_DUPLICATE` directly, without re-running TF-IDF.

**Real methodological finding from development (documented, not patched away):** an early version fit
a fresh `TfidfVectorizer` independently per 2-3-document bucket, which produced unreliably *low*
scores even for genuine near-duplicates (~0.11) — IDF weighting needs a representative corpus size to
be meaningful, and with only 2-3 short documents it systematically suppresses shared vocabulary
instead of highlighting it. **Fix:** fit IDF statistics on the full batch corpus, then only ever
*compare* vectors within a bucket — standard TF-IDF practice, and it kept the spatial/temporal scoping
fully intact while making the IDF math meaningful.

**Second real finding, left honestly unresolved:** even after that fix, this project's own
deliberately-constructed near-duplicate pairs (e.g. "waterlogging near MG Road" vs. "MG Road is
completely flooded" — same real event, different vocabulary) score only ~0.18-0.22 cosine similarity —
real, nonzero signal (clean separation from genuinely unrelated pairs, which score exactly 0.0), but
not high enough to confidently call "the same event." Thresholds were calibrated to these **real
observed numbers**, not tuned to make the fixtures look successful:
```
cosine_similarity >= 0.45  -> SEMANTIC_DUPLICATE   (this project's own paraphrase pairs do NOT reach this)
cosine_similarity >= 0.05  -> POSSIBLE_RELATED_EVENT
cosine_similarity <  0.05  -> UNRELATED
```
TF-IDF is fundamentally a **lexical**-overlap method — it cannot know "waterlogging" and "flooded" mean
similar things. Every deliberately-constructed paraphrase pair in the fixtures lands as
`POSSIBLE_RELATED_EVENT`, correctly distinguished from `UNRELATED` (a real improvement over Phase 3A,
which gave these pairs zero signal at all) but never reaches `SEMANTIC_DUPLICATE`. Closing that gap for
real requires embedding-based semantic similarity — the concrete, evidenced reason this is recommended
for Phase 3C, once model-weight download access exists.

**4. Event classification method.** TF-IDF + Logistic Regression (`class_weight="balanced"`), trained
on the **same labels Phase 3A's keyword heuristic already assigned** (there is no other ground truth in
this project). Stored in a new `predicted_event_category`/`event_classification_confidence` field pair
— it does **not** overwrite the existing `event_type` field, so provenance (rule-based heuristic vs. ML
prediction) is always visible.

**5. Risk/suspicion scoring method.** Explainable, rule-based, additive scoring — never a fake/real
verdict. Signals: `is_suspicious` (Phase 3A's own flag, +0.35), low source reliability <0.35 (+0.25),
low classifier confidence <0.30 (+0.15), a semantic conflict (different `event_type` reported by another
source in the same time+location bucket, +0.30). `verification_status == "REJECTED"` short-circuits to
`risk_score=1.0`/`HIGH_RISK` directly. `risk_label = "UNVERIFIED"` (a risk-sense label, distinct from
`verification_status`'s own `"UNVERIFIED"`) means *insufficient signal exists to compute a risk score at
all* (e.g. empty text and no other signal) — `risk_score` stays `None`, never fabricated. Every
`risk_reasons` entry names the exact signal and its weight.

**Real finding, also left visible rather than hidden:** at this sample size, the classifier's own
max-class confidence is low for nearly every report (observed ~0.19-0.30, even on correctly classified
ones), which means the "low classification confidence" risk signal fires almost universally — reducing
its power to actually *discriminate* risky from non-risky reports right now. This is an expected,
direct consequence of training on very few examples per class, not a bug; the honest fix is more
labeled data, not a recalibrated threshold fit to today's tiny fixture set.

**6. Training/evaluation methodology.** The full labeled corpus (valid, non-empty-text reports with a
known `event_type`) is **21 examples across 8 classes**, several with only 1-2 examples — explicitly too
small for a single fixed train/test split to be statistically meaningful (a handful of examples can
swing accuracy by 10+ points). **Leave-one-out cross-validation** (every example is held out exactly
once) was used instead, as the honest choice at this sample size — not because it produces a bigger or
more flattering number.

**7. Actual results from an actual run (not invented):**
```
Training set size: 21 labeled examples
Class counts: {DUST_STORM: 1, FLOODING: 7, FOG: 3, HEATWAVE: 2, OTHER: 1, RAINFALL: 2, STRONG_WIND: 1, THUNDERSTORM: 4}

Accuracy (LOOCV):          0.6667
Precision (macro, LOOCV):  0.4219
Recall (macro, LOOCV):     0.4643
F1 (macro, LOOCV):         0.4405

Confusion matrix (rows=true, cols=predicted):
labels=[DUST_STORM, FLOODING, FOG, HEATWAVE, OTHER, RAINFALL, STRONG_WIND, THUNDERSTORM]
[0, 0, 1, 0, 0, 0, 0, 0]   <- DUST_STORM (n=1, misclassified as FOG -- impossible to
                               predict correctly under LOOCV with a singleton class, expected)
[0, 5, 0, 0, 0, 2, 0, 0]   <- FLOODING
[0, 0, 3, 0, 0, 0, 0, 0]   <- FOG
[0, 0, 0, 2, 0, 0, 0, 0]   <- HEATWAVE
[0, 0, 0, 0, 0, 1, 0, 0]   <- OTHER (n=1, misclassified as RAINFALL, same reason)
[0, 2, 0, 0, 0, 0, 0, 0]   <- RAINFALL
[0, 1, 0, 0, 0, 0, 0, 0]   <- STRONG_WIND
[0, 0, 0, 0, 0, 0, 0, 4]   <- THUNDERSTORM
```
DUST_STORM and OTHER's misclassifications are exactly what LOOCV honestly exposes for singleton
classes (a class with 1 example can never be correctly predicted under leave-one-out, by construction)
— not hidden, not smoothed over.

Demo run over all 25 reports (15 social + 10 citizen, extended per Phase 3B fixtures below): semantic
similarity — 2 `EXACT_DUPLICATE`, 5 `POSSIBLE_RELATED_EVENT`, 17 `UNRELATED`, 1 unassessed (empty text);
risk — 11 `LOW_RISK`, 11 `MEDIUM_RISK`, 3 `HIGH_RISK`, 0 `UNVERIFIED`; average classification confidence
0.2789.

**8. Fixtures extended (Part G), not replaced.** 8 new social entries (`demo_post_008`–`015`) and 4 new
citizen entries (`citizen_demo_007`–`010`) appended to the existing fixture files — broader event-type
coverage (dust storm, additional thunderstorm/heatwave/fog/rainfall/strong-wind examples), a second
same-city semantic-duplicate pair (Pune rainfall, different wording), a genuinely different-occurrence
same-topic pair (proves the system does not over-merge), a cross-source semantic-duplicate pair (a
citizen report and a social post describing the same Hyderabad thunderstorm), and a clearly-unrelated
control (Bengaluru, clear skies). All new entries carry the same `_synthetic_note` convention as the
original Phase 3A fixtures.

**9. Tests.** `tests/test_phase3b_intelligence.py` — 21 tests covering semantic similarity, exact/near
duplicate detection, temporal and spatial scoping (each tested independently), event classification,
classifier confidence, LOOCV evaluation bounds, risk scoring, the `UNVERIFIED`-vs-`SUSPICIOUS`
distinction, the full orchestration module, and genuine edge cases (below-minimum training size, a
report alone in its bucket, a REJECTED report still getting scored). All pass.

**10. Test results — every phase, actually run in this session:**
```
Phase 2A:  7 passed, 0 failed
Phase 2B: 20 passed, 0 failed
Phase 2C: 17 passed, 0 failed
Phase 3A: 27 passed, 0 failed
Phase 3B: 21 passed, 0 failed
TOTAL:    92 passed, 0 failed
```

**11. Files created:** `src/intelligence/{__init__,semantic_similarity,event_classifier,report_risk,report_intelligence,intelligence_storage}.py`,
`tests/test_phase3b_intelligence.py`, `scripts/run_phase3b_demo.py`, `models/phase3b/README.md`, plus
generated outputs `data/phase3b/intelligent_reports.{json,csv}` and
`models/phase3b/{event_classifier_tfidf_logreg.pkl,event_classifier_metadata.json}`.

**Files modified:** `src/schemas/weather_report.py` (backward-compatible field additions only, verified
against Phase 3A's full test suite before and after), `data/phase3/fixtures/{social_weather_reports.json,citizen_weather_reports.json}`
(appended new entries only, per Part G's explicit permission — one coordinate typo of my own making,
on a newly-added fixture entry, was corrected before it ever appeared in a passing test), and this
README (append-only). **No Phase 1/2A/2B/2C file, and no original Phase 3A fixture entry, was modified
or removed.**

**12. Limitations, stated plainly, per this project's convention of disclosing rather than hiding them:**
- The full labeled corpus is ~21 examples across 8 classes — genuinely too small for production
  accuracy claims. LOOCV was used specifically because a single train/test split would be unreliable
  at this size, not because it's a bigger number.
- TF-IDF cosine similarity is a **lexical**, not semantic, method — it does not reliably recognize
  paraphrases that use different vocabulary for the same concept. Every deliberately-constructed
  near-duplicate pair in the fixtures lands as `POSSIBLE_RELATED_EVENT`, never `SEMANTIC_DUPLICATE`.
- Classifier confidence is uniformly low (~0.19-0.30) at this sample size, which makes the
  "low-confidence" risk signal fire almost universally rather than selectively.
- Singleton/near-singleton classes (DUST_STORM, OTHER, STRONG_WIND at 1 example each) cannot be
  reliably classified — demonstrated, not hidden, in the LOOCV confusion matrix.
- This is a **demo/baseline intelligence layer**, not production social-media verification, not
  fake-news detection, not real-time ingestion, and not ground-truth verification. It requires
  substantially more labeled real-world data before any accuracy claim would be meaningful.

**13. What Phase 3B does NOT claim:** fake news detection is not solved; this is not production-grade
social-media verification; there is no real-time social media ingestion (same synthetic fixtures as
Phase 3A, now extended); no accuracy claim beyond what the actual LOOCV numbers above show; nothing here
constitutes ground-truth verification of any report.

### Running Phase 3B

```bash
python scripts/run_phase3b_demo.py
python tests/test_phase3b_intelligence.py    # 21 tests, all passing
python tests/test_phase3a_reports.py         # Phase 3A's 27 tests, still passing unchanged
python tests/test_phase2c_openmeteo.py       # Phase 2C's 17 tests, still passing unchanged
python tests/test_phase2b_fusion.py          # Phase 2B's 20 tests, still passing unchanged
python tests/test_phase2_ingestion.py        # Phase 2A's 7 tests, still passing unchanged
```

Outputs land in `data/phase3b/` (new directory) and `models/phase3b/` (new directory) — no earlier
phase's output directory is touched.

## Phase 3C — Evidence-Based Corroboration & Verification (COMPLETED)

**1. Purpose.** Phase 3B produced *intelligent* `WeatherReport`s (semantic duplicate detection, event
classification, risk scoring) but never checked a report's claimed event against real weather data.
Phase 3C is exactly the cross-reference Phase 3B's own README recommendation named: does a citizen's
`FLOODING` report actually align with a rainfall spike in the fused ERA5/Open-Meteo/IMD evidence for
the same time and place? It is an entirely additive **corroboration and verification layer**,
`src/corroboration/` (`evidence_mapper.py`, `temporal_evidence.py`, `spatial_evidence.py`,
`report_correlator.py`, `verification_engine.py`, `corroboration_storage.py`), that consumes Phase
2B/2C/2A outputs read-only and Phase 3A/3B `WeatherReport`s read-only.

**Architecture, reused rather than duplicated:**
- `temporal_evidence.py` calls Phase 2B's `fusion.temporal_alignment.check_temporal_match` unmodified
  for the actual match decision (only adds a bisect-indexed candidate search for efficiency over the
  real 17,544-record ERA5/Open-Meteo series).
- `spatial_evidence.py` calls Phase 2B's `fusion.spatial_alignment.check_spatial_match` unmodified, the
  same 25 km default threshold used for ERA5↔IMD comparison.
- `report_correlator.py` loads the **already-generated** Phase 2B/2C JSON outputs
  (`data/phase2/fused/era5_weather_records.json`, `data/phase2c/fused/openmeteo_weather_records.json`)
  rather than re-running the ERA5/Open-Meteo adapters over all 17,544 rows again.
- `verification_engine.py` is the **only** module that assigns a `verification_status` or numeric
  score — every other module in the package only gathers/aligns raw evidence.

**2. Evidence-based weather-event corroboration.** For each `WeatherReport`, Phase 3C asks: is there a
real weather record, close in time and space, whose measured values are consistent with (or contrary
to) what the report claims happened? The answer is always expressed as one of four explicit
verification states (never a binary true/false) plus a transparent, bounded `evidence_support_score`.

**3. WeatherReport → evidence mapping (`evidence_mapper.py`).** A documented, stated lookup from
Phase 3A's controlled `event_type` vocabulary to the `WeatherRecord` fields that can serve as evidence,
split into `required` (must be available or the report is `INSUFFICIENT_EVIDENCE`), `supporting`
(strengthens/weakens the read but its absence alone never blocks a verdict), and `unavailable` (ideal
evidence this project's schema genuinely does not carry, named explicitly rather than silently
skipped — e.g. `FLOODING` has no river-gauge or drainage data, `DUST_STORM` has no visibility or
aerosol data). `RAINFALL`/`THUNDERSTORM`/`FLOODING` map to `rainfall`; `HEATWAVE` maps to
`temperature`; `STRONG_WIND`/`DUST_STORM` map to `wind_speed` (with `wind_gust` supporting); `FOG` has
no required variable at all and falls back to `humidity` as an explicitly flagged weak proxy.

**4. Temporal evidence matching.** Reuses Phase 2B's `check_temporal_match` unchanged; a report's
timestamp is matched against the nearest candidate record in each source's real time series, indexed
with `bisect` for efficiency at 17,544 records per source.

**5. Spatial evidence matching.** Reuses Phase 2B's `check_spatial_match` unchanged, the same 25 km
haversine threshold already used for ERA5↔IMD comparison — no new spatial logic was introduced.

**6. ERA5 evidence.** Phase 2B's fused ERA5 records (`data/phase2/fused/era5_weather_records.json`) —
reanalysis data, not ground truth (see Phase 2B's adapter docstrings) — loaded read-only and indexed
for fast temporal candidate lookup.

**7. Open-Meteo evidence.** Phase 2C's fused Open-Meteo records
(`data/phase2c/fused/openmeteo_weather_records.json`) — a forecast/historical model product, also not
ground truth — loaded and indexed the same way as ERA5.

**8. IMD evidence handling.** Phase 2A's IMD fixture is dated ~2026, not genuine 2024–2025 station
data (a constraint documented since Phase 2A/2B). Because of this, **any report with a real 2024/2025
timestamp gets the explicit reason `IMD_TEMPORAL_UNAVAILABLE` for the IMD source**, never a generic
`NO_TEMPORAL_MATCH` — so "IMD cannot speak to this period" is never confused with "IMD looked and
disagreed."

**9. Verification states** (per `verification_engine.py`, deliberately four distinct outcomes, never
collapsed into VERIFIED/FAKE):
- `SUPPORTED` — available compatible weather evidence is consistent with the report's claimed event.
  Read only as "SUPPORTED BY AVAILABLE WEATHER EVIDENCE," never "this report is true."
- `CONFLICTING` — available compatible weather evidence contradicts the claimed event. Read only as
  "CONFLICTING WITH AVAILABLE WEATHER EVIDENCE," never "this report is fake."
- `UNVERIFIED` — evidence exists but is inconclusive: either all matched sources fall in an ambiguous
  value range, or sources actively disagree with each other (in which case they are **not** blindly
  averaged — both signals are retained in the reasons).
- `INSUFFICIENT_EVIDENCE` — no usable evidence at all: missing timestamp, missing location, no
  temporally/spatially matched record in any source, an event category with no evidence mapping, or
  the required variable unavailable in every matched record.

**10. `evidence_support_score` is NOT a probability of truth.** It is a plain, transparent mean of
per-source numeric verdict codes (`SUPPORTING_EVIDENCE=1.0`, `AMBIGUOUS_EVIDENCE=0.5`,
`CONFLICTING_EVIDENCE=0.0`) taken only over sources that actually had a usable, matched value. It is
`None`, never invented, when no source has usable evidence for that report. ERA5 and Open-Meteo are
themselves model/reanalysis products, not ground truth, so even a `SUPPORTED` verdict is at most
cross-model/observational consistency, never proof.

**11. Real Phase 3C output statistics** (from `scripts/run_phase3c_demo.py`, saved to
`data/phase3c/{corroborated_reports.json,corroborated_reports.csv,verification_summary.json}`):
```
Combined demo totals across all 33 reports (25 real Phase 3A/3B fixtures + 8 controlled edge cases):
  INSUFFICIENT_EVIDENCE: 28
  SUPPORTED:              3
  CONFLICTING:            1
  UNVERIFIED:             1

average_evidence_support_score (over the 5 reports that received a score): 0.7
evidence_source_usage_counts: ERA5: 5, Open-Meteo: 5
```
Part 1 of the demo script runs the real 25 Phase 3A/3B synthetic fixture reports against the real
Phase 2B/2C evidence — **all 25 resolve to `INSUFFICIENT_EVIDENCE`** (explained in Limitations below).
Part 2 uses 8 small, clearly-labeled controlled edge-case fixtures timestamped inside the real
2024–2025 evidence window to prove the verification logic itself works correctly against real data,
including a genuine multi-source disagreement at `2024-01-05T15:00:00Z` — ERA5 shows 0.80 mm rainfall,
Open-Meteo shows 0.0 mm at the exact same real hour/location — correctly resolved to `UNVERIFIED`
rather than averaged away.

**12. Known limitations, stated plainly:**
- **Zero temporal overlap in the real fixture set.** Phase 3A's 25 synthetic fixture reports are dated
  2026 (fabricated posting times), while the real ERA5/Open-Meteo evidence only covers
  2024-01-01–2025-12-31. This is why all 25 resolve to `INSUFFICIENT_EVIDENCE` — see item 13.
- **Real 2024–2025 Jabalpur wind speed never reaches the 10.8 m/s `STRONG_WIND` support threshold**
  (max observed: ERA5 ≈7.95 m/s, Open-Meteo ≈9.31 m/s). This behavior is proven in the test suite via a
  small, clearly-labeled synthetic `EvidenceSource` fixture rather than real data — itself a useful,
  honestly-documented data point about this project's real wind climatology, not worked around by
  lowering the threshold to fit.
- **IMD contributes no usable evidence for any real-dated report**, since its only data is the ~2026
  fixture (`IMD_TEMPORAL_UNAVAILABLE`, see item 8).
- **Evidence thresholds (item 9's support/conflict values) are documented, stated defaults, not
  scientifically calibrated** against verified ground-truth outcomes — same discipline as Phase 2B's
  `PERCENT_THRESHOLDS` and Phase 2C's pressure-threshold finding.
- **FOG's evidence is a weak, indirect humidity proxy** (no directly diagnostic variable exists in this
  project's schema); verdicts for FOG are explicitly flagged with extra caution in their reasons.
- **FLOODING and DUST_STORM verdicts are indirect** (rainfall / wind-speed proxies respectively) — this
  project has no river-gauge, drainage, visibility, or aerosol data, so a supported verdict means
  "consistent with a rain/wind event," not confirmation of flooding or dust specifically.

**13. Why reports with no temporal overlap correctly become `INSUFFICIENT_EVIDENCE`.** This is the
system working as designed, not a bug. Phase 3C's temporal matching (item 4) reuses Phase 2B's
`check_temporal_match` unmodified, which only returns a match when a report's timestamp falls within
that function's configured window of an actual evidence record. Phase 3A's fixture reports carry 2026
posting timestamps because they were authored as synthetic demo data, not sampled from the real
2024–2025 evidence period; no evidence record exists anywhere near 2026, in any of ERA5, Open-Meteo, or
the IMD fixture. Rather than loosen the temporal window to force a match — which would silently
compare a report against weather from a different day/period and produce a meaningless verdict — the
engine correctly reports `INSUFFICIENT_EVIDENCE` with the specific unavailable reason for every source.
Part 2's controlled edge-case fixtures (item 11) exist precisely to demonstrate, on data that *does*
overlap the real evidence window, that `SUPPORTED`/`CONFLICTING`/`UNVERIFIED` all work correctly when
evidence is actually available.

**14. Future work.** See "Recommended Next Step: Phase 4" below.

**Tests.** `tests/test_phase3c_corroboration.py` — 21 tests covering the evidence mapping table, temporal
and spatial matching (independently), ERA5/Open-Meteo/IMD loading, the `IMD_TEMPORAL_UNAVAILABLE` vs.
generic `NO_TEMPORAL_MATCH` distinction, all four verification states, `evidence_support_score`
computation and its `None` case, weak-proxy flagging, and Phase 3B field preservation. All pass.

**Files created:** `src/corroboration/{__init__,evidence_mapper,temporal_evidence,spatial_evidence,
report_correlator,verification_engine,corroboration_storage}.py`, `scripts/run_phase3c_demo.py`,
`tests/test_phase3c_corroboration.py`, plus generated outputs in `data/phase3c/`.

**Files modified:** This README (append-only, new Phase 3C section) and `PS69_HANDOFF_DOCUMENT.md`.
**No Phase 1/2A/2B/2C/3A/3B file was modified, renamed, or removed** — Phase 3C is entirely additive
and consumes earlier phases' outputs read-only.

### Running Phase 3C

```bash
python scripts/run_phase3c_demo.py
python -m pytest -q                            # all 113 tests, every phase, offline
```

Outputs land in `data/phase3c/` (new directory) — no earlier phase's output directory is touched.

## Phase 4A — Unified Weather Intelligence Layer (COMPLETED)

**Purpose.** A clean, unified representation that brings together Phase 2B/2C fusion, Phase 3B
intelligence, and Phase 3C corroboration into one object per time/place, so later phases (forecasting,
anomaly detection, alerting) have a single consistent thing to consume instead of four separate
pipelines' raw outputs. New package `src/phase4/` (`weather_intelligence.py`, `intelligence_storage.py`)
— entirely additive; it imports and reuses Phase 2B's `fusion.temporal_alignment`/`spatial_alignment`
functions and consumes Phase 2B/2C fusion results and Phase 3C verification results exactly as they
already exist. No Phase 1/2A/2B/2C/3A/3B/3C file was modified.

**`WeatherIntelligence` fields, per the spec:** `timestamp`/`latitude`/`longitude`/`country`/`state`/
`district`/`city`; `weather_variables` (temperature/humidity/pressure/rainfall/wind_speed/
wind_direction — the same fields `WeatherRecord` already defines, never a new invented variable);
`contributing_sources`; `source_agreement_confidence`/`source_agreement_match_status`/
`source_agreement_details`/`source_agreement_marginal` (copied unmodified from Phase 2B/2C's
`fuse_pair()` output, `None` for a single-source record); `report_evidence` (a trimmed list of matching
Phase 3C `verify_report()` results); `corroboration_status` (a rollup — see below);
`evidence_support_score` (transparent mean of the matched reports' own scores); `overall_confidence`
(see below); `forecast`/`anomaly`/`alert` (fields exist, per explicit instruction, but are always `None`
— Phase 4A does not implement forecasting, anomaly detection, or alerting).

**Corroboration rollup, applied to a SET of reports rather than Phase 3C's single-report logic:** no
matched report evidence → `INSUFFICIENT_EVIDENCE`; both `SUPPORTED` and `CONFLICTING` present among
matched reports → `CONFLICTING` (the disagreement is the honest signal, never averaged into
`UNVERIFIED`); only `CONFLICTING` present → `CONFLICTING`; `SUPPORTED` present with no `CONFLICTING`/
`UNVERIFIED` → `SUPPORTED`; anything else (e.g. `UNVERIFIED` present) → `UNVERIFIED`.

**`overall_confidence`, documented exactly:** the mean of whichever of `source_agreement_confidence`
and `evidence_support_score` are not `None`. Both present → their mean. Only one present → that value
exactly (never padded for the missing one). Neither present → `None`, never fabricated. Every record's
own `confidence_method` field spells out which case applied. `overall_confidence` is explicitly **not**
a probability that the underlying weather event is true — it is a transparent average of two
already-explainable component scores.

**Real demo (`scripts/run_phase4a_demo.py`):** fuses real ERA5+Open-Meteo records (via Phase 2B's own
`fuse_pair()`, unmodified) at the 5 real 2024–2025 timestamps where Phase 3C's own demo produced a
non-`INSUFFICIENT_EVIDENCE` verdict, attaches those real Phase 3C results, and saves the result —
`SUPPORTED: 3, UNVERIFIED: 1, CONFLICTING: 1`, matching Phase 3C's own status counts for those 5
reports exactly. Outputs: `data/phase4/weather_intelligence.{json,csv}`.

**Known limitation, stated plainly:** the demo only builds real fused records at those 5 real
timestamps (Phase 3C's own controlled edge-case fixtures — not real citizen/social reports), not
across the full 17,544-row real series; doing so would be a straightforward extension of the same
loop, left for a future phase. `tests/test_phase4a_intelligence.py` (27 tests, synthetic fixtures)
covers every corroboration/confidence code path independently of that limitation.

**Tests.** `tests/test_phase4a_intelligence.py` — 27 tests: object creation, single-source vs. fused
multi-source variables, provenance, all four corroboration rollup outcomes, confidence calculation and
its "never fabricated" cases, unmatched fusion, serialization round-trip, and storage round-trip. All
pass; combined with the pre-existing 113, the full suite is **140 passed, 0 failed**.

### Running Phase 4A

```bash
python scripts/run_phase4a_demo.py
python -m pytest -q                            # all 140 tests, every phase, offline
```

**STOP — Phase 4A is complete. Do not start Phase 4B or Phase 4C without explicit user instruction.**

## Phase 4B — Advanced Machine Learning Layer (COMPLETED)

**Objective.** Build the advanced multi-horizon ML layer on top of Phase 1's baseline ML, without
replacing it. New package `src/phase4b/` (`feature_engineering.py`, `time_series_ml.py`,
`model_persistence.py`, `intelligence_integration.py`) — entirely additive. No Phase 1/2A/2B/2C/3A/
3B/3C/4A file was modified.

**Architecture (per the spec):**
```
Historical Weather Data (data/processed/jabalpur_clean.csv, real, 17,544 rows)
        -> Feature engineering (widened lag/rolling cols, reusing Phase 1's own functions)
        -> Chronological TRAIN -> VALIDATION -> TEST split (Phase 1's own chronological_split(),
           called twice: train/val, then val/test)
        -> Baseline model (RandomForest, same family/hyperparameters Phase 1 used)
        -> Advanced model (HistGradientBoosting)
        -> Multi-horizon prediction (1h, 3h, 6h, 12h, 24h)
        -> Evaluation (Phase 1's own regression_report()/classification_report_dict())
        -> Model comparison table (data/phase4b/model_comparison.csv)
        -> Saved production-ready artifacts (models/phase4b/{temperature,rainfall}/*.pkl + .json metadata)
        -> WeatherIntelligence integration (fills Phase 4A's pre-existing, previously-None `forecast` field)
```

**Feature engineering (Part A/B).** Phase 1's own inspected baseline (notebook 05): target
`target_t2m_h1` (temperature 1h ahead), features = cyclical hour/day-of-year + lags {1,2,3,6,12,24}h
of `t2m_c`/`msl_hpa`/`wind_speed`/`d2m_c` + rolling {3,6,24}h mean/std of `t2m_c`/`msl_hpa`/`tp_mm`,
chronological 70/15/15 split, RandomForest(n_estimators=200, max_depth=12), evaluated with
MAE/RMSE/R². Phase 4B reuses those exact functions (`add_cyclical_time_features`, `add_lag_features`,
`add_rolling_features`, `add_target_temperature` from `src/features/build_features.py`, unmodified)
and widens the lag/rolling column set to include `relative_humidity_approx` and `fg10` (wind gust) —
both already present in the real cleaned dataset — then builds the same target at 5 horizons instead
of 1, and a parallel rain-occurrence target (`target_rain_next{h}h`, generalising Phase 1's own
`rain_flag.shift(-1)` pattern) at the same 5 horizons, preserving Phase 1's `rain_flag` threshold
(`tp_mm > 0.1`) unmodified.

**Leakage prevention, stated exactly (Part B):** every feature column uses only observations at or
before time t (lags with `shift(lag)`, lag ≥ 1; rolling stats with `shift(1).rolling(w)`, so the
window never includes the current row). Only the target column looks forward, via `shift(-h)`, and it
is excluded from every model's feature list. Verified in `tests/test_phase4b_ml.py::test_no_leakage_lag_and_rolling`
by confirming a feature value at row i is identical whether computed on the full series or a series
truncated right after row i.

**Validation strategy (Part E).** TRAIN → VALIDATION → TEST, chronological, via Phase 1's own
`chronological_split(train_frac=0.7, val_frac=0.15)` — never a random `train_test_split`. Headline
metrics below are reported on the TEST split only, matching Phase 1's own reporting convention.

**Models compared (Part C/D/F), real data, all 5 horizons — full table in
`data/phase4b/model_comparison.csv`/`.json`:**

*Temperature (MAE °C, test split):*

| Horizon | NaivePersistence | RandomForest | HistGradientBoosting |
|---|---|---|---|
| 1h  | 0.964 | 0.436 | **0.364** |
| 3h  | 2.535 | 0.700 | **0.688** |
| 6h  | 4.397 | 0.975 | **0.891** |
| 12h | 6.294 | **0.902** | 0.908 |
| 24h | 0.894 | **0.938** | 1.004 |

*Rainfall occurrence (F1 / ROC-AUC, test split, positive rate ≈ 11–12% at every horizon):*

| Horizon | RandomForest F1 | RandomForest ROC-AUC | HistGB F1 | HistGB ROC-AUC |
|---|---|---|---|---|
| 1h  | 0.736 | 0.967 | **0.745** | **0.974** |
| 3h  | 0.574 | 0.936 | **0.625** | **0.938** |
| 6h  | 0.481 | **0.920** | **0.524** | 0.918 |
| 12h | 0.452 | 0.908 | **0.539** | **0.908** |
| 24h | 0.429 | 0.897 | **0.476** | **0.903** |

**Baseline comparison (Part C, honest, not cherry-picked):** Phase 1's own recorded 1h Random Forest
result (`reports/findings.md`) is MAE 0.439 / RMSE 0.621 / R² 0.989. Phase 4B's 1h RandomForest, on a
widened feature set, measured MAE 0.436 / RMSE 0.613 / R² 0.989 — materially the same, not a dramatic
improvement, because both models are the same algorithm/hyperparameters on nearly the same features.
Phase 4B's 1h HistGradientBoosting measured MAE 0.364 / RMSE 0.509 / R² 0.992 — a real improvement, but
the comparison is **not** a strict apples-to-apples ablation (Phase 4B's feature set is wider than
Phase 1's), so this is reported as an honest directional result, not a rigorous causal claim. Longer
horizons were not evaluated in Phase 1 at all — there is no Phase 1 number to compare 3h/6h/12h/24h
against; those results are new, not "improvements."

**Model persistence (Part G).** 20 model files under `models/phase4b/{temperature,rainfall}/` (10
horizon/target combinations × {RandomForest, HistGradientBoosting}), each `<model>_h<horizon>.pkl`
paired with a `.json` metadata file recording model type, target, horizon, full feature list, training
date/data-range, evaluation metrics, preprocessing description, and random seed (42, same seed Phase 1
used). `tests/test_phase4b_ml.py::test_model_persistence_and_reload` confirms a saved model loads and
reproduces its original predictions exactly.

**Phase 4A integration (Part H), backward-compatible only.** Phase 4A's `WeatherIntelligence.forecast`
field existed but was always `None` ("a LATER phase has a place to put results"). Phase 4B's
`src/phase4b/intelligence_integration.py` fills that field — never redesigning the dataclass, its
builder, or its storage format — with real per-horizon temperature/rainfall-probability predictions
from the saved HistGradientBoosting models. `scripts/run_phase4b_demo.py` loads Phase 4A's real 5
records from `data/phase4/weather_intelligence.json` (untouched on disk) and attaches a real forecast
to the 3 whose timestamps fall inside the real dataset's leakage-safe (post lag-warm-up) window; the
other 2 are honestly skipped rather than fabricated, with the reason printed. Output:
`data/phase4b/weather_intelligence_with_forecast.json`. The `forecast` dict is explicit that it is
**not** real-time (it is a batch prediction from a saved model) and that `rainfall_probability` is a
model-predicted class probability, **not** a probability of truth.

**Tests (Part I).** `tests/test_phase4b_ml.py` — 14 tests on small deterministic synthetic fixtures
(feature generation, lag correctness, rolling correctness, chronological splitting, leakage
prevention, missing-value handling, temperature/rainfall model training, multi-horizon support, metric
calculation, model persistence + reload, reproducibility, Phase 4A `forecast`-field compatibility).
Real data is used only for the actual evaluation (`scripts/run_phase4b_demo.py`), never for these unit
tests. Combined with the pre-existing 140, the full suite is **154 passed, 0 failed**.

**Outputs.** `data/phase4b/model_comparison.{csv,json}` (the full 30-row comparison table), `data/
phase4b/forecast_results.json` (best model per target/horizon), `data/phase4b/metrics.json` (headline
1h baseline-vs-Phase-4B numbers), `data/phase4b/weather_intelligence_with_forecast.json` (3 real
integrated records). `data/phase4/` and `data/processed/` are untouched.

**Limitations, stated plainly:**
- Phase 4B's feature set is wider than Phase 1's, so the 1h comparison above is honest but not a
  strict same-features ablation.
- Single grid point (Jabalpur, ERA5 only) — the same scope limitation Phase 1 documented.
- Rainfall F1 degrades with horizon (0.75 at 1h → 0.48 at 24h, HistGB) — stated directly, not hidden;
  longer-horizon rain occurrence is a genuinely harder problem with this feature set and one location.
- `HistGradientBoosting` was run with lightly-set hyperparameters (`max_iter=200`, `random_state=42`)
  — no hyperparameter search was performed for this SIH demonstration.
- This machine's single CPU core meant the full 10-combination training run was executed as separate
  per-horizon runs of `scripts/_phase4b_worker.py` (identical logic to `run_phase4b_demo.py`, just
  invoked once per target/horizon to fit within available execution time); `run_phase4b_demo.py`
  itself trains everything in one pass when run standalone with enough time/CPU, and reuses the
  already-saved results if `scripts/_phase4b_worker.py` was run first.

### Running Phase 4B

```bash
python scripts/run_phase4b_demo.py     # trains everything in one pass if not already trained
python -m pytest -q                    # all 154 tests, every phase, offline
```

**STOP — Phase 4B is complete. Do not start Phase 4C or Phase 4D without explicit user instruction.**

## Phase 4C — Weather Anomaly Detection + Explainable Anomaly Analytics (COMPLETED)

**Objective.** Turn raw/normalized weather observations into an explainable anomaly-detection layer
for temperature, wind_speed, rainfall, and pressure — without ever claiming a statistical anomaly is
automatically a disaster, emergency, confirmed extreme-weather event, or warning. New package
`src/phase4c/` (`anomaly_features.py`, `anomaly_scoring.py`, `anomaly_detection.py`,
`anomaly_storage.py`) plus `scripts/run_phase4c_demo.py` and `tests/test_phase4c_anomaly_detection.py`
— entirely additive. No Phase 1–4B file was modified.

**Classification discipline (stated exactly, per the spec).** Every finding's `classification` field
is the literal string `STATISTICAL_ANOMALY` (or `NORMAL`) — never `DISASTER`/`EMERGENCY`/`CYCLONE`/
`FLOOD`/`HEATWAVE`/`TORNADO`. This project has no existing convention for a more specific statistical
label, so the generic one is used everywhere, per the spec's explicit instruction.

**Architecture:**
```
Normalized WeatherRecord observations (ERA5, Open-Meteo — Phase 2B/2C adapters, reused unmodified)
        -> records_to_dataframe() — per-SOURCE sort + dedupe (never merges sources)
        -> per-variable causal rolling detectors:
             temperature / wind_speed / pressure -> rolling z-score  (anomaly_detection.py)
             rainfall                             -> rolling percentile (zero-inflation-aware)
        -> AnomalyRecord (explainable: observed value, baseline, deviation, method, threshold,
           score, severity, classification, deterministic explanation string)
        -> data/phase4c/anomalies.json / .csv / anomaly_summary.json
        -> additive integration: WeatherIntelligence.anomaly field (Phase 4A), observed-anomaly
           context on forecast records (Phase 4B)
```

**Source separation (a non-negotiable design choice, not just a convenience).** Every detector
operates on ONE source's own time series at a time — `run_anomaly_detection()` groups input by
`source` before calling any detector, and no rolling baseline is ever built from more than one
source's values. This is also what keeps the Phase 2C pressure caveat from ever leaking in as a
false anomaly here (see "Pressure" below).

**Causality / leakage prevention.** Every rolling baseline for row *t* uses `.shift(1).rolling(window)`
— only rows strictly before *t* — the identical convention Phase 4B's `feature_engineering.py`
already documents and uses for its own ML features. `tests/test_phase4c_anomaly_detection.py::
test_reproducibility_same_input_same_output` and `::test_insufficient_history_for_first_n_records`
assert this directly.

**Methods, per variable:**
- **Temperature / Wind speed** — causal rolling mean/std over a configurable window (default 168
  hours = 7 days, `AnomalyConfig.zscore_window`/`zscore_min_periods`), `z = (observed - rolling_mean)
  / rolling_std`, anomaly when `|z| >= z_threshold` (default 3.0 — the standard "three-sigma"
  outlier convention). A rolling std below `zero_variance_epsilon` (default 1e-6) is treated as
  undefined and reported as `ZERO_VARIANCE`, never divided by.
- **Rainfall** — **not** z-score. Rainfall is zero-inflated (most hours are 0 mm), so an ordinary
  mean/std z-score would flag ordinary light rain as "extreme" simply because the baseline mean sits
  near 0 with a tiny std. Instead: causal rolling 50th/95th percentile (`rainfall_window` default 720
  hours = 30 days, `rainfall_min_periods` default 168), `score = (observed - p95) / max(p95 - p50,
  epsilon)`, anomaly when `observed > p95` and `score >= rainfall_threshold` (default 1.0).
  `rainfall_epsilon` (default 0.1 mm, matching typical rain-gauge/reanalysis resolution) prevents
  division by ~0 in dry windows. `tests/test_phase4c_anomaly_detection.py::
  test_rainfall_percentile_anomaly_on_zero_inflated_series` confirms ordinary light showers are not
  flagged once the rolling baseline reflects them as normal, while a genuine downpour still is.
- **Pressure** — same rolling z-score method as temperature/wind, **plus an explicit, documented
  caveat**: Phase 2C found that ERA5's pressure field is mean-sea-level pressure (`msl`) while
  Open-Meteo's is `surface_pressure`, systematically ~35–46 hPa lower at Jabalpur's ~390m elevation
  (see the Phase 2C section above). Because Phase 4C never compares sources to each other — each
  source's baseline is built purely from its own past pressure values — this definitional mismatch
  cannot itself produce a false anomaly here. This is asserted directly by
  `test_pressure_caveat_not_triggered_by_cross_source_definition_mismatch`, and every pressure
  `AnomalyRecord.explanation` includes the caveat text as a standing reminder for anyone reading the
  output later.

**Severity.** A step function of "how many multiples of the variable's own base threshold was this
deviation" — `ratio = score / threshold`; `ratio < 2.0` → LOW, `< 3.0` → MEDIUM, `< 4.0` → HIGH,
`>= 4.0` → CRITICAL (`AnomalyConfig.severity_ratio_low/medium/high`). This is a transparent,
configurable convention for ranking anomalies by size — **not** a claim about real-world danger level.

**Edge cases, all handled with an honest status rather than a fabricated score:**

| Status | Meaning |
|---|---|
| `EVALUATED` | Enough history existed; a real score was computed. |
| `INSUFFICIENT_HISTORY` | Fewer than `min_periods` valid prior observations in the rolling window (always true for the first `window` rows of a series). |
| `ZERO_VARIANCE` | Rolling std ≈ 0 (constant window) — z-score undefined. |
| `MISSING_VALUE` | The observation itself is `None`/NaN. |
| `INVALID_VALUE` | Rainfall observed as negative (physically impossible) — excluded from both scoring and the rolling baseline, never silently dropped from the record count. |

Duplicate timestamps are deduplicated (first occurrence kept, count reported); unsorted input is
sorted by timestamp before any rolling computation; every one of these is covered by its own test.

**Real-data results** (`scripts/run_phase4c_demo.py`, ERA5 + Open-Meteo, Jabalpur, 2024–2025, real
17,544-row series per source, loaded via the existing unmodified Phase 2B/2C adapters):

| Metric | Value |
|---|---|
| Total observations analyzed (both sources, 4 variables) | 140,352 |
| Total statistical anomalies | 1,309 (rate 0.93%) |
| By variable | temperature 28, wind_speed 418, pressure 170, rainfall 693 |
| By source | ERA5 677, Open-Meteo 632 |
| By severity | LOW 865, MEDIUM 134, HIGH 61, CRITICAL 249 |
| Insufficient-history count | 1,344 (the first 168–720 rows of each source/variable, as designed) |
| Missing/invalid/zero-variance count | 0 / 0 / 0 (the real dataset has no gaps or negative rainfall) |

Rainfall anomalies concentrate in the monsoon season (647 of 693, i.e. ~93%) — the expected real-world
pattern, not an artifact. No single variable dominates the anomaly count implausibly, and the two
sources' anomaly counts are comparable without being suspiciously identical — both checked manually
per the spec's "scientific validation" requirement before this section was written.

**Output files** (`data/phase4c/`, a new directory — nothing from earlier phases was overwritten):
`anomalies.json`/`.csv` (only the actual `STATISTICAL_ANOMALY` findings — persisting all ~140k
per-hour `NORMAL` evaluations would be a multi-hundred-MB file of near-zero information content; the
full counts already live in the summary), `anomaly_summary.json` (all counts above, computed from the
real run, not manufactured), `weather_intelligence_with_anomalies.json` and
`forecast_with_anomaly_context.json` (see integration below).

**Phase 4A integration (additive).** `attach_anomalies_to_intelligence()` fills Phase 4A's
pre-existing, previously-`None` `WeatherIntelligence.anomaly` field, reusing the exact same
`check_temporal_match`/`check_spatial_match` alignment functions Phase 4A's own
`select_report_evidence()` already uses for report evidence — no new matching logic invented. A
record's `anomaly` field stays `None` when nothing aligns in time/place; it is never fabricated. In
the demo, 1 of the 5 existing Phase 4A demo records had a matching anomaly nearby.

**Phase 4B integration (additive, context-only).** `attach_anomaly_context_to_forecast()` adds an
`observed_anomaly_context` list to a copy of a Phase 4B forecast record — it never edits the
forecast's own predicted value and never labels a forecasted value as an observed anomaly; forecast
and observation stay conceptually separate, per the spec. In the demo, 1 of the 3 forecast records had
observed-anomaly context nearby.

**Tests.** `tests/test_phase4c_anomaly_detection.py` — 21 tests on small, hand-authored, deterministic
synthetic fixtures, covering: normal values, an obvious temperature/wind/rainfall/pressure anomaly,
the pressure cross-source-mismatch non-trigger, missing values, insufficient history, zero variance,
boundary threshold behavior, duplicate-timestamp dedup, unsorted-input sorting, reproducibility,
source separation, severity scaling, explanation-text generation, a storage round-trip, the Phase
4A/4B integration functions, and a real-data smoke test (skipped gracefully if the real data file
isn't present in a given checkout).

**Limitations, stated honestly:**
- Window sizes (168h / 720h) and thresholds (z=3.0, rainfall score=1.0) are documented, reasonable,
  standard-convention defaults — not fitted/validated against any labeled ground-truth anomaly set,
  because no such labels exist in this project. They are fully configurable via `AnomalyConfig`.
- The rolling-window methods used here (mean/std, quantile) do not account for seasonality within the
  window itself — a window spanning a rapid seasonal transition (e.g. late winter into pre-monsoon)
  will have a wider "normal" range than either sub-period alone, which could under-flag genuine
  anomalies right at a seasonal transition. This is a known limitation of simple rolling-window
  methods, not a bug; a seasonally-decomposed baseline would be a reasonable Phase 4D candidate.
- Only ERA5 and Open-Meteo (both already-integrated real sources) were run through the demo; the IMD/
  citizen-report pipelines from earlier phases were not re-run through Phase 4C, since they don't
  carry the same dense hourly time series a rolling-window method needs.

**STOP — Phase 4C is complete. Do not start Phase 4D without explicit user instruction.**
