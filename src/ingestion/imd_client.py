"""
IMD API client for PS69 Phase 2.

Uses ONLY verified, currently-documented endpoints from IMD's own API
reference (https://api.imd.gov.in/public/api_reference.html), fetched and
checked directly as part of this project's research — no invented or
guessed endpoints.

IMPORTANT — verified access reality (checked 2026-08-29):
IMD's real-time REST APIs (api.imd.gov.in/api/v1/...) require IP
whitelisting. A direct test call to current_wx without whitelisting
returned HTTP 401. This client calls the real endpoints and honestly
reports that failure rather than silently falling back or pretending
success. A `use_fixtures=True` mode is provided purely so the rest of the
pipeline (validation -> schema -> storage) can be exercised and demonstrated
without live access; fixture data is clearly sourced (see
data/phase2/fixtures/) and never presented as live.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

IMD_BASE_URL = "https://api.imd.gov.in/api/v1"
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "phase2" / "fixtures"

# Verified endpoint paths (from api.imd.gov.in/public/api_reference.html)
ENDPOINT_CURRENT_WX = f"{IMD_BASE_URL}/current_wx"
ENDPOINT_AWS_DATA = f"{IMD_BASE_URL}/aws_data"


class IMDAccessError(Exception):
    """Raised when IMD's API rejects the request (e.g. IP not whitelisted)."""
    pass


class IMDClient:
    def __init__(self, use_fixtures: bool = False, timeout: int = 15):
        """
        use_fixtures: if True, read from data/phase2/fixtures/ instead of
        calling the live API. Use this for offline development/testing
        until IP whitelisting is granted. Default is False — by default
        this client attempts the REAL endpoint and reports honestly if it
        fails, it does not silently substitute fixture data.
        """
        self.use_fixtures = use_fixtures
        self.timeout = timeout

    def _load_fixture(self, filename: str) -> List[Dict[str, Any]]:
        path = FIXTURES_DIR / filename
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]

    def get_current_weather(self, station_id: str) -> List[Dict[str, Any]]:
        """Calls the verified current_wx endpoint. Raises IMDAccessError with
        a clear message if the API rejects the request (e.g. not whitelisted)."""
        if self.use_fixtures:
            return self._load_fixture("imd_current_wx_fixture.json")

        try:
            resp = requests.get(
                ENDPOINT_CURRENT_WX, params={"id": station_id}, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise IMDAccessError(f"Network error calling IMD current_wx: {e}") from e

        if resp.status_code == 401 or resp.status_code == 403:
            raise IMDAccessError(
                f"IMD current_wx returned {resp.status_code}. This endpoint requires "
                f"IP whitelisting (see https://mausam.imd.gov.in/responsive/apis.php -> "
                f"'For IP Whitelisting'). Request whitelisting for your server's static "
                f"IP, or pass use_fixtures=True for offline development."
            )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else [data]

    def get_aws_data(self, call_sign: Optional[str] = None,
                      state_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Calls the verified aws_data endpoint (station-level or state-level).
        Raises IMDAccessError with a clear message if the API rejects the request."""
        if self.use_fixtures:
            return self._load_fixture("imd_aws_data_sample.json")

        params = {}
        if call_sign:
            params["id"] = call_sign
        if state_id:
            params["sid"] = state_id

        try:
            resp = requests.get(ENDPOINT_AWS_DATA, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise IMDAccessError(f"Network error calling IMD aws_data: {e}") from e

        if resp.status_code == 401 or resp.status_code == 403:
            raise IMDAccessError(
                f"IMD aws_data returned {resp.status_code}. This endpoint requires "
                f"IP whitelisting (see https://mausam.imd.gov.in/responsive/apis.php -> "
                f"'For IP Whitelisting'). Request whitelisting for your server's static "
                f"IP, or pass use_fixtures=True for offline development."
            )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else [data]
