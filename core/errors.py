"""
Standardized Platform Exceptions and Error Response Envelopes.
Reference: Architecture Report Section 4.1.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional
from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Standard API error payload envelope."""
    error: str = Field(description="Machine-readable error identifier")
    detail: str = Field(description="Human-readable description")
    request_id: Optional[str] = Field(default=None, description="Correlation identifier for tracing")
    timestamp: str = Field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())
    context: Optional[dict[str, Any]] = Field(default=None, description="Optional diagnostic context")


class FishIntelError(Exception):
    """Base exception for domain-level application errors."""
    error_code: str = "internal_error"
    status_code: int = 500

    def __init__(
        self,
        detail: str,
        *,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        self.context = context or {}


class UpstreamUnavailable(FishIntelError):
    """Raised when an external data provider or model upstream fails or times out."""
    error_code: str = "upstream_unavailable"
    status_code: int = 503

    def __init__(
        self,
        service: str,
        detail: Optional[str] = None,
        *,
        retry_after: int = 30,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        msg = detail or f"Upstream service '{service}' is temporarily unavailable."
        ctx = context or {}
        ctx["service"] = service
        ctx["retry_after"] = retry_after
        super().__init__(msg, context=ctx)
        self.service = service
        self.retry_after = retry_after


class ResourceNotFound(FishIntelError):
    """Raised when an entity or resource is not found."""
    error_code: str = "not_found"
    status_code: int = 404


class AuthenticationFailed(FishIntelError):
    """Raised when authentication credentials are invalid or expired."""
    error_code: str = "authentication_failed"
    status_code: int = 401


class InsufficientPermissions(FishIntelError):
    """Raised when an authenticated principal lacks required scope or role."""
    error_code: str = "forbidden"
    status_code: int = 403
