"""Research artifact catalog and safe downloads for Analyst/Admin users."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from backend.api.auth.rbac import require_analyst
from backend.api.schemas import ResearchArtifact, ResearchArtifactListResponse, ResearchArtifactPreviewResponse

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]

# Explicit allow-list. Never accept arbitrary filesystem paths from a request.
ARTIFACTS: dict[str, dict[str, str]] = {
    "jabalpur-weather-2024-2025": {
        "name": "Jabalpur weather observations 2024–2025",
        "path": "data/raw/jabalpur_weather_2024_2025.csv",
        "category": "SOURCE DATA",
        "description": "Historical Jabalpur weather dataset used as the core 2024–2025 analytical input.",
    },
    "jabalpur-openmeteo-2024-2025": {
        "name": "Jabalpur Open-Meteo 2024–2025",
        "path": "data/raw/jabalpur_openmeteo_2024_2025.json",
        "category": "SOURCE DATA",
        "description": "Historical Open-Meteo source records for cross-source analysis.",
    },
    "jabalpur-clean": {
        "name": "Jabalpur cleaned weather records",
        "path": "data/processed/jabalpur_clean.csv",
        "category": "PROCESSED DATA",
        "description": "Cleaned and normalized weather records used downstream in feature engineering.",
    },
    "temperature-features": {
        "name": "Temperature features",
        "path": "data/processed/features_temperature.csv",
        "category": "PROCESSED DATA",
        "description": "Feature-engineered temperature dataset used by the forecast models.",
    },
    "rainfall-features": {
        "name": "Rainfall features",
        "path": "data/processed/features_rain.csv",
        "category": "PROCESSED DATA",
        "description": "Feature-engineered rainfall dataset used by the rainfall classifier.",
    },
    "era5-records": {
        "name": "ERA5 weather records",
        "path": "data/phase2/fused/era5_weather_records.csv",
        "category": "DATA FUSION",
        "description": "ERA5 historical weather records ingested into the analytics database.",
    },
    "openmeteo-records": {
        "name": "Open-Meteo weather records",
        "path": "data/phase2c/fused/openmeteo_weather_records.csv",
        "category": "DATA FUSION",
        "description": "Open-Meteo historical weather records ingested into the analytics database.",
    },
    "era5-openmeteo-fused": {
        "name": "ERA5 + Open-Meteo fused records",
        "path": "data/phase2c/fused/era5_openmeteo_fused_records.csv",
        "category": "DATA FUSION",
        "description": "Temporally and spatially aligned cross-source records.",
    },
    "era5-openmeteo-comparison": {
        "name": "ERA5 + Open-Meteo comparison",
        "path": "data/phase2c/fused/era5_openmeteo_comparison.csv",
        "category": "DATA FUSION",
        "description": "Variable-level agreement/disagreement comparison between ERA5 and Open-Meteo.",
    },
    "phase2c-summary": {
        "name": "Multi-source fusion summary",
        "path": "data/phase2c/fused/phase2c_summary.json",
        "category": "DATA FUSION",
        "description": "Fusion coverage, agreement statistics and scientific notes.",
    },
    "intelligent-reports": {
        "name": "Intelligent weather reports",
        "path": "data/phase3b/intelligent_reports.json",
        "category": "WEATHER INTELLIGENCE",
        "description": "Classified reports with duplicate, risk and semantic similarity metadata.",
    },
    "corroborated-reports": {
        "name": "Corroborated reports",
        "path": "data/phase3c/corroborated_reports.json",
        "category": "CORROBORATION",
        "description": "Reports evaluated against external weather evidence and alignment checks.",
    },
    "verification-summary": {
        "name": "Corroboration verification summary",
        "path": "data/phase3c/verification_summary.json",
        "category": "CORROBORATION",
        "description": "Evidence status distribution, source usage and evidence-score summary.",
    },
    "weather-intelligence": {
        "name": "Weather intelligence records",
        "path": "data/phase4/weather_intelligence.json",
        "category": "WEATHER INTELLIGENCE",
        "description": "Cross-source weather intelligence records with confidence and corroboration context.",
    },
    "weather-intelligence-forecast": {
        "name": "Weather intelligence + forecast",
        "path": "data/phase4b/weather_intelligence_with_forecast.json",
        "category": "FORECAST & MODELS",
        "description": "Weather intelligence enriched with forecast/model outputs.",
    },
    "weather-intelligence-anomalies": {
        "name": "Weather intelligence + anomaly context",
        "path": "data/phase4c/weather_intelligence_with_anomalies.json",
        "category": "ANOMALIES",
        "description": "Weather intelligence enriched with Phase 4C anomaly context.",
    },
    "anomalies": {
        "name": "Detected anomalies",
        "path": "data/phase4c/anomalies.csv",
        "category": "ANOMALIES",
        "description": "Flagged statistical anomalies detected by the Phase 4C pipeline.",
    },
    "anomaly-summary": {
        "name": "Anomaly analysis summary",
        "path": "data/phase4c/anomaly_summary.json",
        "category": "ANOMALIES",
        "description": "Anomaly rate, severity, variable, season and preprocessing statistics.",
    },
    "forecast-results": {
        "name": "Forecast results",
        "path": "data/phase4b/forecast_results.json",
        "category": "FORECAST & MODELS",
        "description": "Best-model forecast results across temperature and rainfall horizons.",
    },
    "model-comparison": {
        "name": "Forecast model comparison",
        "path": "data/phase4b/model_comparison.csv",
        "category": "FORECAST & MODELS",
        "description": "Model-level MAE, RMSE, R², precision, recall, F1 and ROC-AUC metrics.",
    },
    "model-metrics": {
        "name": "Model metrics summary",
        "path": "data/phase4b/metrics.json",
        "category": "FORECAST & MODELS",
        "description": "Saved model count, horizons and headline metrics.",
    },
    "findings": {
        "name": "Analytical findings",
        "path": "reports/findings.md",
        "category": "REPORTS",
        "description": "Documented analytical findings and caveats from the existing pipeline.",
    },
    "timeseries-figure": {
        "name": "Time-series overview",
        "path": "reports/fig_timeseries_overview.png",
        "category": "REPORTS",
        "description": "Existing analytical time-series figure from the weather dataset.",
    },
    "feature-importance": {
        "name": "Temperature feature importance",
        "path": "reports/fig_feature_importance_temp.png",
        "category": "REPORTS",
        "description": "Existing temperature model feature-importance visualization.",
    },
    "correlation-matrix": {
        "name": "Weather correlation matrix",
        "path": "reports/fig_correlation_matrix.png",
        "category": "REPORTS",
        "description": "Existing weather-variable correlation visualization.",
    },
}


def _safe_path(artifact_id: str) -> Path:
    spec = ARTIFACTS.get(artifact_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Research artifact not found")
    path = (REPO_ROOT / spec["path"]).resolve()
    if REPO_ROOT not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Research artifact is unavailable")
    return path


def _row_count(path: Path) -> int | None:
    if path.suffix.lower() != ".csv":
        return None
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _artifact_payload(artifact_id: str) -> ResearchArtifact:
    spec = ARTIFACTS[artifact_id]
    path = _safe_path(artifact_id)
    suffix = path.suffix.lower().lstrip(".")
    return ResearchArtifact(
        artifact_id=artifact_id,
        name=spec["name"],
        category=spec["category"],
        format=suffix.upper(),
        size_bytes=path.stat().st_size,
        row_count=_row_count(path),
        description=spec["description"],
        source_path=spec["path"],
        download_endpoint=f"/research/artifacts/{artifact_id}/download",
    )


@router.get("/artifacts", response_model=ResearchArtifactListResponse)
def list_artifacts(current_user: dict = Depends(require_analyst)) -> ResearchArtifactListResponse:
    artifacts = [_artifact_payload(artifact_id) for artifact_id in ARTIFACTS]
    return ResearchArtifactListResponse(artifacts=artifacts)


@router.get("/artifacts/{artifact_id}/preview", response_model=ResearchArtifactPreviewResponse)
def preview_artifact(
    artifact_id: str,
    limit: int = Query(30, ge=1, le=50),
    current_user: dict = Depends(require_analyst),
) -> ResearchArtifactPreviewResponse:
    path = _safe_path(artifact_id)
    suffix = path.suffix.lower()
    rows: list[Any] = []
    columns: list[str] = []
    artifact = _artifact_payload(artifact_id)

    if suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            for row in reader:
                rows.append(dict(row))
                if len(rows) >= limit:
                    break
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            sample = payload[:limit]
            rows = sample
            if sample and isinstance(sample[0], dict):
                columns = list(sample[0].keys())
        elif isinstance(payload, dict):
            columns = ["key", "value"]
            rows = [{"key": key, "value": value} for key, value in list(payload.items())[:limit]]
        else:
            columns = ["value"]
            rows = [{"value": payload}]
    elif suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8")[:12000]
        rows = [{"text": text}]
        columns = ["text"]
    else:
        return ResearchArtifactPreviewResponse(artifact=artifact, columns=[], rows=[])

    return ResearchArtifactPreviewResponse(artifact=artifact, columns=columns, rows=rows)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, current_user: dict = Depends(require_analyst)) -> FileResponse:
    path = _safe_path(artifact_id)
    return FileResponse(path=path, filename=path.name)
