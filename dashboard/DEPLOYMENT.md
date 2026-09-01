# PS69 Dashboard — Deployment & Live Weather

## Static deployment

The dashboard is intentionally a static frontend. It can be deployed to Netlify, Vercel, GitHub Pages, or any static hosting service without a Python backend.

Use the repository root as the publish directory if the host serves the whole repository. The dashboard URL is `/dashboard/`.

For a quick local test:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/dashboard/`.

## What is live vs historical

- **Live Weather panel:** calls Open-Meteo from the browser and can switch between Jabalpur, Indore, Bhopal, New Delhi, Mumbai, or the user's browser location.
- **Research analytics:** the Phase 1–4C charts, anomaly history, corroboration and trained-model metrics continue to use the validated project datasets. Selecting another city does not pretend that the historical research dataset changed.

This separation is deliberate: it gives judges a working live product demo while keeping the scientific results traceable to the actual data used in the project.

## Future production architecture

A production version should put a small API layer in front of external providers and the analytics pipeline. That backend can accept latitude/longitude, fetch current + forecast observations, run the trained models/anomaly engine, store observations, and return a unified `WeatherIntelligence` response. The current frontend is already structured so the live-data function can be replaced by API calls later.

## Important

The live weather feature requires internet access. If the external provider is unavailable, the historical analytics pages still work from the repository JSON outputs.
