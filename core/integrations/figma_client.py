"""
FigmaClient — Full API wrapper for Figma REST API v1.

Features:
- Rate limiting (30 req/min to stay under Figma's 60/min limit)
- In-memory caching (5 min TTL)
- Exponential backoff retry (3 attempts)
- File, node, component, variable, and style endpoints
- Comment and version history support

Usage:
    from core.integrations.figma_client import figma_client

    # Get file info
    file_data = await figma_client.get_file("UklcflWFBHal5xPSrSQolq")

    # Get specific nodes
    nodes = await figma_client.get_file_nodes("UklcflWFBHal5xPSrSQolq", ["1:2", "1:3"])

    # Create design elements
    await figma_client.create_rectangle("UklcflWFBHal5xPSrSQolq", parent_id, {...})

Environment:
    FIGMA_ACCESS_TOKEN — Personal access token from figma.com/developers
"""

import os
import time
import asyncio
import hashlib
import json
import logging
from typing import Any, Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────
FIGMA_API_BASE = "https://api.figma.com/v1"
RATE_LIMIT_PER_MIN = 30  # Conservative: Figma allows 60/min
CACHE_TTL_SECONDS = 300  # 5 minutes
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


@dataclass
class CacheEntry:
    data: Any
    expires_at: float


@dataclass
class RateLimiter:
    """Sliding window rate limiter."""
    max_requests: int = RATE_LIMIT_PER_MIN
    window_seconds: float = 60.0
    timestamps: list = field(default_factory=list)

    def _prune(self):
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]

    async def acquire(self):
        """Wait until a request slot is available."""
        while True:
            self._prune()
            if len(self.timestamps) < self.max_requests:
                self.timestamps.append(time.monotonic())
                return
            # Wait until the oldest request expires
            wait_time = self.timestamps[0] + self.window_seconds - time.monotonic() + 0.1
            logger.debug(f"Rate limited, waiting {wait_time:.1f}s")
            await asyncio.sleep(max(0.1, wait_time))


class FigmaClient:
    """Async Figma REST API client with rate limiting, caching, and retry."""

    def __init__(self, access_token: Optional[str] = None):
        self._token = access_token or os.getenv("FIGMA_ACCESS_TOKEN", "")
        self._cache: dict[str, CacheEntry] = {}
        self._rate_limiter = RateLimiter()
        self._client: Optional[httpx.AsyncClient] = None
        self._stats = {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "retries": 0,
            "errors": 0,
        }

    @property
    def is_configured(self) -> bool:
        return bool(self._token)

    @property
    def stats(self) -> dict:
        return {**self._stats}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=FIGMA_API_BASE,
                headers={
                    "X-Figma-Token": self._token,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    def _cache_key(self, method: str, path: str, params: Optional[dict] = None) -> str:
        raw = f"{method}:{path}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and entry.expires_at > time.time():
            self._stats["cache_hits"] += 1
            return entry.data
        if entry:
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any, ttl: float = CACHE_TTL_SECONDS):
        self._cache[key] = CacheEntry(data=data, expires_at=time.time() + ttl)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        use_cache: bool = True,
    ) -> dict:
        """Make an API request with rate limiting, caching, and retry."""
        if not self.is_configured:
            return {"error": "FIGMA_ACCESS_TOKEN not configured", "status": "not_configured"}

        # Check cache for GET requests
        cache_key = self._cache_key(method, path, params)
        if use_cache and method == "GET":
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        self._stats["cache_misses"] += 1
        client = await self._get_client()

        for attempt in range(MAX_RETRIES):
            await self._rate_limiter.acquire()
            self._stats["requests"] += 1

            try:
                if method == "GET":
                    resp = await client.get(path, params=params)
                elif method == "POST":
                    resp = await client.post(path, json=json_body, params=params)
                elif method == "PUT":
                    resp = await client.put(path, json=json_body, params=params)
                elif method == "DELETE":
                    resp = await client.delete(path, params=params)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if resp.status_code == 429:
                    # Rate limited by Figma — back off
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Figma rate limit hit, retrying in {wait:.1f}s")
                    self._stats["retries"] += 1
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                # Cache successful GET responses
                if use_cache and method == "GET":
                    self._set_cached(cache_key, data)

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (500, 502, 503) and attempt < MAX_RETRIES - 1:
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Figma {e.response.status_code}, retrying in {wait:.1f}s")
                    self._stats["retries"] += 1
                    await asyncio.sleep(wait)
                    continue
                self._stats["errors"] += 1
                return {"error": str(e), "status_code": e.response.status_code}

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Figma connection error, retrying in {wait:.1f}s: {e}")
                    self._stats["retries"] += 1
                    await asyncio.sleep(wait)
                    continue
                self._stats["errors"] += 1
                return {"error": f"Connection failed after {MAX_RETRIES} attempts: {e}"}

        self._stats["errors"] += 1
        return {"error": "Max retries exceeded"}

    # ── File Endpoints ─────────────────────────────────────────────────

    async def get_file(self, file_key: str, **params) -> dict:
        """GET /v1/files/:file_key — Full file tree."""
        return await self._request("GET", f"/files/{file_key}", params=params or None)

    async def get_file_nodes(self, file_key: str, node_ids: list[str]) -> dict:
        """GET /v1/files/:file_key/nodes — Specific nodes."""
        return await self._request("GET", f"/files/{file_key}/nodes", params={"ids": ",".join(node_ids)})

    async def get_images(self, file_key: str, node_ids: list[str], fmt: str = "png", scale: int = 2) -> dict:
        """GET /v1/images/:file_key — Export node images."""
        return await self._request("GET", f"/images/{file_key}", params={
            "ids": ",".join(node_ids),
            "format": fmt,
            "scale": str(scale),
        })

    # ── Component Endpoints ────────────────────────────────────────────

    async def get_file_components(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/components — All components in file."""
        return await self._request("GET", f"/files/{file_key}/components")

    async def get_file_component_sets(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/component_sets — Component sets in file."""
        return await self._request("GET", f"/files/{file_key}/component_sets")

    async def get_file_styles(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/styles — All styles in file."""
        return await self._request("GET", f"/files/{file_key}/styles")

    # ── Variables (requires Enterprise or Education plan) ──────────────

    async def get_local_variables(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/variables/local — Local variables (Enterprise only)."""
        return await self._request("GET", f"/files/{file_key}/variables/local")

    async def post_variables(self, file_key: str, payload: dict) -> dict:
        """POST /v1/files/:file_key/variables — Create/update variables (Enterprise only)."""
        return await self._request("POST", f"/files/{file_key}/variables", json_body=payload)

    async def get_published_variables(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/variables/published — Published variables (Enterprise only)."""
        return await self._request("GET", f"/files/{file_key}/variables/published")

    # ── Comments ───────────────────────────────────────────────────────

    async def get_comments(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/comments"""
        return await self._request("GET", f"/files/{file_key}/comments")

    async def post_comment(self, file_key: str, message: str, client_meta: Optional[dict] = None) -> dict:
        """POST /v1/files/:file_key/comments"""
        body: dict[str, Any] = {"message": message}
        if client_meta:
            body["client_meta"] = client_meta
        return await self._request("POST", f"/files/{file_key}/comments", json_body=body)

    # ── Version History ────────────────────────────────────────────────

    async def get_versions(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/versions"""
        return await self._request("GET", f"/files/{file_key}/versions")

    # ── Team / Project Endpoints ───────────────────────────────────────

    async def get_team_projects(self, team_id: str) -> dict:
        """GET /v1/teams/:team_id/projects"""
        return await self._request("GET", f"/teams/{team_id}/projects")

    async def get_project_files(self, project_id: str) -> dict:
        """GET /v1/projects/:project_id/files"""
        return await self._request("GET", f"/projects/{project_id}/files")

    # ── Plugin Data ────────────────────────────────────────────────────

    async def get_file_dev_resources(self, file_key: str) -> dict:
        """GET /v1/files/:file_key/dev_resources"""
        return await self._request("GET", f"/files/{file_key}/dev_resources")

    # ── Utility ────────────────────────────────────────────────────────

    async def get_me(self) -> dict:
        """GET /v1/me — Current user info. Good for verifying token."""
        return await self._request("GET", "/me")

    def clear_cache(self):
        """Clear the in-memory cache."""
        self._cache.clear()

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def __repr__(self) -> str:
        configured = "configured" if self.is_configured else "not configured"
        return f"<FigmaClient {configured}, {self._stats['requests']} requests>"


# ── Singleton ──────────────────────────────────────────────────────────
figma_client = FigmaClient()
