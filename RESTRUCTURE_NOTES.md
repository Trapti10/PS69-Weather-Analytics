# Repository Restructure Notes (post-Phase 7)

This document records a structural cleanup performed after Phase 7. No
Phase 1–7 logic, endpoints, or frontend behavior was changed — only file
locations, import paths, and build/deploy configuration were touched, and
only where required to keep everything working after the move.

> **Provenance note:** an earlier pass of this cleanup was done against the
> GitHub repo clone, which had accumulated some local debris (a committed
> Windows `.venv/`, some stray shell-redirection artifact files, and an
> orphaned CSV zip) that isn't present in this package, since this package
> was built directly from the actual local project export instead. Every
> other file was verified byte-identical between the two sources, so the
> structural changes below apply the same way. This export also uses a
> leaner `.gitignore` and doesn't include `.env.example` files — both
> reflect the actual project's current state as provided, not something
> this cleanup removed.

## What changed

### 1. Removed
- **`dashboard/`** — the old static HTML/CSS/JS dashboard. Verified via a
  full-repo reference search that nothing in the Phase 7 frontend or the
  backend imported, served, or linked to it before deleting it.
- **Root `index.html`** — it only existed to redirect `/` to `/dashboard/`
  and had no purpose once `dashboard/` was removed.

(The GitHub clone of this repo separately had a committed 374 MB Windows
`.venv/`, some stray shell-artifact files, and an orphaned CSV zip at the
root — none of that debris is in this package, since it was built from
the clean local project export.)

### 2. Renamed: `phase5/` → `backend/`
This is the FastAPI + PostgreSQL/PostGIS backend (originally scaffolded in
Phase 5, extended in Phase 6 and Phase 7). Only the folder name and every
reference to it changed — no endpoint, model, or business logic was
touched:
- All internal imports (`from phase5.api...` → `from backend.api...`)
  across `backend/api/**`, `backend/db/migrate_from_json.py`, and
  `backend/tests/**`.
- `backend/api/main.py`'s `uvicorn.run("phase5.api.main:app", ...)` →
  `"backend.api.main:app"`.
- `Dockerfile`, `docker-compose.yml`, `setup_phase5.sh`,
  `setup_phase5.ps1`, `backend/setup.sh`, `backend/SETUP.md`,
  `backend/API.md` — all path references updated.
- `requirements-phase5.txt` (root, an older/duplicate dependency list) was
  moved to `backend/requirements-legacy.txt` for reference; the actively
  used file remains `backend/requirements.txt` (was `phase5/requirements.txt`,
  unchanged in content).

**Verified after the rename:**
- `from backend.api.main import app` imports successfully and all routers
  (auth, reports, events, admin) register correctly.
- All 24 DB-independent backend unit tests pass
  (`backend/tests/test_phase5_unit.py`).
- All 175 pre-existing Phase 1–4C tests still pass unmodified (`tests/`).
- The Phase 7 frontend builds cleanly (`npm run build`) and all 33
  Vitest tests pass, unaffected since it only talks to the backend via
  `VITE_API_BASE_URL`, never via a file path.

**Not verified in this environment (no PostgreSQL/Docker available in
this sandbox):**
- `backend/tests/test_phase5_integration.py`
- `backend/tests/test_phase6_admin_verification.py`
- `backend/tests/test_phase7_event_coordinates.py`
- `backend/tests/test_phase7_my_reports.py`

These require a live PostgreSQL + PostGIS instance (`docker compose up -d
postgres`) and were not run here. Nothing about the rename should affect
them — the `sys.path` calculations these files rely on
(`Path(__file__).resolve().parents[3] / "src"`) resolve to the same
absolute path as before, because `backend/` sits at the same depth `phase5/`
did — but please run them yourself before treating the backend as fully
verified:
```
docker compose up -d postgres
pip install -r backend/requirements.txt
pytest backend/tests/ -v
```

### 3. Deliberately left at the repository root (not moved into `backend/`)
`src/`, `data/`, `models/`, `scripts/`, `tests/`, `reports/`, `notebooks/`.

These were **not** moved into `backend/` even though most are consumed by
it, because:
- `backend/api/routes/reports.py`, `backend/db/migrate_from_json.py`, and
  every file in `backend/tests/` locate `src/` via a hardcoded relative
  path count from their own file location. Moving `src/` would require
  editing that path math in every one of those files — a much larger,
  riskier change than a folder rename, for no functional benefit.
- Root-level `tests/` (Phase 1–4C unit tests) and `scripts/` (Phase 1–4C
  demo scripts) locate `src/` the same way, and are independent of the
  backend — they exist and are useful even if the API is never run.
- `backend/api/config.py` reads `data/` via `./data/...`, relative to the
  process's working directory (wherever you run `uvicorn` or `pytest`
  from), not relative to the backend package's location — so `data/`
  staying at the root, with the backend still run from the repo root, is
  what the existing (unmodified) config already expects.

In short: `src/`, `data/`, `models/`, `scripts/`, `tests/`, `reports/`,
and `notebooks/` are shared foundation/assets used by the backend and by
standalone tooling alike, so they stay at the top level rather than being
nested under one consumer.

### 4. `vercel.json`
Previously configured for the removed static `dashboard/` (`buildCommand:
null`, implying a static deploy of the repo root). Updated to build the
Phase 7 frontend instead:
```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": "vite"
}
```

## Final top-level layout
```
PS69-Weather-Analytics/
├── frontend/           Phase 7 React app (unchanged internals)
├── backend/            FastAPI + PostgreSQL/PostGIS API (was phase5/)
├── src/                Phase 1–4C pipeline modules (shared by backend, scripts, tests)
├── data/                Raw/processed data + fixtures (shared)
├── models/              Trained ML artifacts (Phase 3B/4B)
├── scripts/             Phase 1–4C demo/ingestion scripts
├── tests/               Phase 1–4C unit tests
├── reports/             Phase 1 baseline figures + findings
├── notebooks/           Phase 1 exploration/modeling notebooks
├── docker-compose.yml
├── vercel.json
├── .env.example
├── .gitignore
├── requirements.txt          (Phase 1–4C / notebook dependencies)
├── setup_phase5.sh / .ps1    (alternate setup flow; backend/setup.sh is primary)
├── README.md, PS69_HANDOFF_DOCUMENT.md, PHASE5_*.md   (historical phase docs, untouched)
└── RESTRUCTURE_NOTES.md      (this file)
```

## Note on documentation
`README.md`, `PS69_HANDOFF_DOCUMENT.md`, and the `PHASE5_*.md` files are
historical, completed-phase deliverables and were **not** rewritten as
part of this cleanup (per this project's additive-only rule). Where they
mention a `phase5/...` path in prose, read it as `backend/...` per the
mapping above.
