# PS69 – Weather Analytics — Phase 1 Findings

**Dataset:** ERA5 reanalysis (Copernicus CDS), single grid point — Jabalpur, India (23.25°N, 80.0°E)
**Period:** 2024-01-01 to 2025-12-31, hourly resolution
**Rows / columns:** 17,544 × 10 (raw) → 26 (after cleaning + derived fields)

> **Scope note:** This is explicitly a **Phase 1 baseline**, not the full PS69 solution. It uses a
> single source (ERA5) and a single location to prove out the methodology — ingestion, cleaning,
> feature engineering, chronological modeling, evaluation. The target architecture fuses ERA5 + IMD +
> MOSDAC + AWS stations + radar into one platform; this notebook set is the first working slice of it.

## 1. Data Quality

| Check | Result |
|---|---|
| Missing values | 0 |
| Duplicate rows | 0 |
| Duplicate timestamps | 0 |
| Missing hourly timestamps | 0 (17,544 / 17,544 expected) |
| Physical range checks | All variables within plausible bounds |

The raw download was a **ZIP archive saved with a `.csv` extension** (standard Copernicus CDS
behaviour) — handled transparently in `src/data/load_clean.py::load_raw()`.

The dataset's near-perfect quality reflects that ERA5 is *model-reanalysis* data, not raw sensor
telemetry — the missing-data / faulty-sensor problem central to the original fragmentation problem
statement will reappear once real IMD/AWS/radar feeds are fused in during later phases.

## 2. Key Statistics

- **Temperature:** 7.0°C – 43.9°C, mean 25.6°C — consistent with Jabalpur's climate
- **Pressure:** 992.2 – 1022.9 hPa
- **Rainfall:** heavily zero-inflated — 84% of hours have zero precipitation; ~85% of 2-year total
  rainfall falls in the Jun–Sep monsoon window
- **Wind:** mean 2.3 m/s, gusts up to 16.0 m/s
- **Extreme rain days (>64.5mm/day, IMD "heavy rain" threshold):** only **2 out of 731 days**
- **Lag-1 autocorrelation:** temperature 0.975, pressure 0.995, wind speed 0.922

## 3. ML Problem Comparison

| Problem | Target | Evidence | Verdict |
|---|---|---|---|
| A. Short-term temperature forecast | t2m, 1–24h ahead | Autocorrelation 0.975, zero missing data | **Selected as primary Phase-1 baseline** |
| B. Rain/no-rain occurrence | rain_flag, next 1–24h | 11.5% positive rate (workable imbalance) | **Selected as secondary track** |
| C. Heavy rainfall event detection | daily rain > 64.5mm | Only 2 positive days / 731 | **Deferred to Phase 2** — too few positives for a reliable baseline |
| D. Pressure-anomaly rain-onset signal | — | msl correlates -0.26 with rain, -0.67 with temp | Used as a **feature**, not a standalone target yet |

## 4. Baseline Model Results (chronological train/val/test split, never shuffled)

### Track A — Temperature forecast, 1h ahead (test set, Sep–Dec 2025)

| Model | MAE (°C) | RMSE (°C) | R² |
|---|---|---|---|
| Naive persistence (t+1 = t) | 0.964 | 1.489 | 0.935 |
| Linear Regression | 0.709 | 0.926 | 0.975 |
| **Random Forest** | **0.439** | **0.621** | **0.989** |

Random Forest cuts MAE by more than half versus the naive baseline and explains 98.9% of variance —
a strong, honestly-evaluated result on held-out future data.

### Track B — Rain occurrence, next hour (test set)

Test-set positive rate: 11.5%

| Model | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|
| Naive "always no rain" | 0.0 | 0.0 | 0.0 | — |
| **Random Forest (class-weighted)** | **0.732** | **0.828** | **0.777** | **0.973** |

The class-weighted Random Forest substantially outperforms the trivial baseline on an imbalanced
target, with strong ROC-AUC.

## 5. Limitations (stated explicitly, not hidden)

- Single grid point — not a spatial forecast; results are specific to this Jabalpur coordinate
- Single source (ERA5 only) — no ground-truth AWS/IMD cross-validation performed yet
- Only 2 years of data — extreme/rare events (cyclones, heavy rain >100mm/day) are under-represented
- Heavy-rain classification (Problem C) intentionally not attempted as a Phase-1 baseline given the
  evidence above — flagged as a Phase 2 goal once multi-source, multi-location fusion increases the
  number of observed extreme events

## 6. Proposed Architecture (target state beyond Phase 1)

```
ERA5 + IMD + MOSDAC + weather stations + satellite/radar
        ↓
  Data ingestion
        ↓
  Data standardization
        ↓
  Data quality checks
        ↓
  Data fusion
        ↓
  Analytics / ML
        ↓
  Risk intelligence
        ↓
  GIS dashboard / alerts
```

Phase 1 (this repo) implements the ingestion → cleaning → feature engineering → analytics/ML → evaluation
slice for a single source, proving the methodology before scaling to multi-source fusion.

## 7. Implementation Plan (next phases)

1. **Phase 2 — multi-source ingestion:** add IMD API (JSON) and MOSDAC (NetCDF/GeoTIFF) connectors;
   handle differing formats/resolutions/update frequencies
2. **Phase 3 — spatial-temporal fusion:** align sources to a common grid/time-bucket (PostGIS,
   xarray); add real missing/faulty-data detection (range checks, spike detection, cross-station
   validation) since real sensor data will not be as clean as ERA5
3. **Phase 4 — extreme event modeling:** revisit heavy-rainfall/cyclone detection once multi-location
   fusion provides enough positive examples
4. **Phase 5 — serving layer:** GIS dashboard, hyperlocal alerts, regional-language support (directly
   addressing the accessibility gaps identified in the original problem research)
