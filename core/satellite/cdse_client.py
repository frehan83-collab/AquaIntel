"""
Copernicus Data Space Ecosystem (CDSE) Sentinel Hub Client
==========================================================
Replaces the `sentinelhub` python package to avoid heavy C-dependencies
(shapely, geos) which are blocked by Windows Device Guard and bloat the container.

Provides OAuth2 token management (cached) and Sentinel-2 Statistical API queries.
"""
from __future__ import annotations

import datetime as dt
import httpx
import structlog
from typing import Optional

from config.settings import settings

log = structlog.get_logger(__name__)

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

class CDSEClient:
    def __init__(self):
        self._client_id = settings.sentinel_hub_client_id
        self._client_secret = settings.sentinel_hub_client_secret
        self._token: str | None = None
        self._token_expires: dt.datetime | None = None

    async def _get_token(self) -> str:
        """Fetch or return cached OAuth token."""
        if not self._client_id or not self._client_secret:
            raise ValueError("CDSE credentials not configured (SENTINEL_HUB_CLIENT_ID/SECRET).")
            
        now = dt.datetime.now(dt.UTC)
        if self._token and self._token_expires and now < self._token_expires:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            # Typically 600 seconds, cushion by 60s
            expires_in = data.get("expires_in", 600)
            self._token_expires = now + dt.timedelta(seconds=max(60, expires_in - 60))
            log.info("cdse.token_refreshed", expires_in=expires_in)
            return self._token

    async def fetch_farm_stats(self, lat: float, lon: float, days_back: int = 10) -> Optional[dict]:
        """Fetch Sentinel-2 L2A water quality stats via Statistical API."""
        try:
            token = await self._get_token()
        except ValueError as e:
            log.debug("cdse.skipped", reason=str(e))
            return None
        except Exception as e:
            log.error("cdse.token_failed", error=str(e))
            return None

        # ~500m buffer
        delta = 0.005
        bbox = [lon - delta, lat - delta, lon + delta, lat + delta]
        end_date = dt.datetime.now(dt.UTC)
        start_date = end_date - dt.timedelta(days=days_back)

        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{bands: ["B02","B03","B04","B08","B11","SCL"]}],
                output: {bands: 5, sampleType: "FLOAT32"}
            };
        }
        function evaluatePixel(s) {
            let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + 0.0001);
            let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 0.0001);
            let turbidity = s.B04 / (s.B03 + 0.0001);
            let cloud = (s.SCL == 8 || s.SCL == 9 || s.SCL == 3) ? 1.0 : 0.0;
            return [ndwi, ndvi, turbidity, cloud, s.B08];
        }
        """

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
                },
                "data": [
                    {
                        "dataFilter": {"timeRange": {"from": start_date.isoformat(), "to": end_date.isoformat()}},
                        "type": "sentinel-2-l2a"
                    }
                ]
            },
            "aggregation": {
                "timeRange": {"from": start_date.isoformat(), "to": end_date.isoformat()},
                "aggregationInterval": {"of": "P1D"},
                "evalscript": evalscript,
                "resx": 10,
                "resy": 10
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    STATS_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            log.error("cdse.api_error", status=e.response.status_code, body=e.response.text[:200])
            return None
        except Exception as e:
            log.error("cdse.fetch_error", error=str(e)[:200])
            return None

cdse_client = CDSEClient()
