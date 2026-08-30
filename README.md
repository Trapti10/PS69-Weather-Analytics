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
"# PS69-Weather-Analytics" 
