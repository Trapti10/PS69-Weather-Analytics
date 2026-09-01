# PS69 Weather Intelligence Dashboard

This dashboard is an **additive frontend layer**. It does not modify or replace the existing Phase 2–4C Python pipeline, models, data, tests, or scripts.

## Run it safely

From the repository root:

```bash
python -m http.server 8000
```

Then open:

`http://localhost:8000/dashboard/`

The UI reads the existing repository outputs directly:

- `data/phase4c/anomaly_summary.json`
- `data/phase4c/anomalies.json`
- `data/phase4/weather_intelligence.json`
- `data/phase4b/metrics.json`
- `data/phase4b/forecast_results.json`
- `data/phase3c/verification_summary.json`

## Important

Do **not** open `dashboard/index.html` directly with `file://` because browsers block local JSON fetches. Use the local HTTP server above.

The dashboard is intentionally read-only. When an API/backend is added later, the data-loading layer in `app.js` can be replaced with API calls without changing the existing analytics pipeline.
