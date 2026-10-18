"""Official NOK exchange rates — one licensed source for the money paths.

Why this module exists (WS-31, 2026-10-18)
------------------------------------------
The margin bridge, the feed cost engine and the competitiveness engine converted NOK
figures at a USD/NOK rate taken from Yahoo Finance. Yahoo's API terms forbid using its
data to "derive income" without written permission, so a paid product cannot price
Norwegian costs from it — and to be precise about the licence rather than the price,
the rate also arrived without an observation date.

Norges Bank publishes the official daily NOK rates as open data (SDMX-JSON) with the
observation date attached. One definition here, used by every NOK conversion, with a
documented constant fallback that is *recorded* rather than silent (the WS-22 rule:
a fallback must degrade the payload, never ride a live label).

The endpoint is public and needs no key::
    https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?format=sdmx-json&lastNObservations=1
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

NORGES_BANK_URL = (
    "https://data.norges-bank.no/api/data/EXR/B.{currency}.NOK.SP"
    "?format=sdmx-json&lastNObservations=1"
)
SOURCE_NAME = "Norges Bank EXR (official daily NOK exchange rate)"

#: Currencies this platform converts. Norges Bank quotes NOK per unit of foreign
#: currency, which is the inverse of the USD-per-NOK convention the engines use.
SUPPORTED = ("USD", "EUR", "GBP", "DKK", "SEK", "PLN")

#: Emergency constants, used only when the official feed is unreachable. Every caller
#: must surface ``is_fallback`` when it gets one (the payload degrades).
FALLBACK_NOK_PER_USD = 10.5

_CACHE_TTL = dt.timedelta(hours=1)
_cache: dict[str, tuple[dt.datetime, dict]] = {}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _parse_sdmx(payload: Any) -> tuple[float | None, str | None]:
    """(rate in NOK per unit of foreign currency, ISO observation date).

    SDMX-JSON shape: ``data.dataSets[0].series["0:0:0:0"].observations`` maps an
    index to ``[value]``; the matching period is in
    ``data.structure.dimensions.observation[0].values[i].id``.
    """
    try:
        data = payload["data"]
        series = next(iter(data["dataSets"][0]["series"].values()))
        index, values = next(iter(series["observations"].items()))
        rate = float(values[0])
        observed = None
        try:
            observed = data["structure"]["dimensions"]["observation"][0]["values"][
                int(index)
            ]["id"]
        except (KeyError, IndexError, TypeError, ValueError):
            observed = None
        return rate, observed
    except (KeyError, IndexError, StopIteration, TypeError, ValueError):
        return None, None


async def nok_rate(currency: str = "USD", *, timeout: float = 8.0) -> dict:
    """NOK per one unit of ``currency``, with its observation date.

    Returns ``{"currency", "nok_per_unit", "observed_at", "source", "is_fallback",
    "fallback_reason"}``. ``is_fallback`` is True only when the official feed could not
    be read; the constant is then named in ``fallback_reason``.
    """
    code = (currency or "USD").strip().upper()
    cached = _cache.get(code)
    if cached and (_now() - cached[0]) < _CACHE_TTL:
        return cached[1]

    result: dict = {
        "currency": code,
        "nok_per_unit": None,
        "observed_at": None,
        "source": SOURCE_NAME,
        "is_fallback": False,
        "fallback_reason": None,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                NORGES_BANK_URL.format(currency=code),
                headers={"User-Agent": "AquaIntel/1.0 (contact: platform operator)"},
            )
        if response.status_code == 200:
            rate, observed = _parse_sdmx(response.json())
            if rate and rate > 0:
                result.update({"nok_per_unit": rate, "observed_at": observed})
                _cache[code] = (_now(), result)
                return result
            reason = "the official feed answered without a usable observation"
        else:
            reason = f"the official feed answered HTTP {response.status_code}"
    except Exception as exc:  # noqa: BLE001 — the caller must still get a number
        reason = f"the official feed was unreachable ({str(exc)[:80]})"

    fallback = FALLBACK_NOK_PER_USD if code == "USD" else None
    result.update(
        {
            "nok_per_unit": fallback,
            "is_fallback": True,
            "fallback_reason": (
                reason
                + (f"; fell back to the constant {fallback} NOK per {code}"
                   if fallback else "; no constant is defined for this currency")
            ),
        }
    )
    log.warning("fx.nok_rate_fallback", currency=code, reason=reason)
    return result


async def usd_nok() -> dict:
    """Convenience wrapper for the rate every money path needs."""
    return await nok_rate("USD")


def clear_cache() -> None:
    """Drop the memo (tests and an operator-triggered refresh)."""
    _cache.clear()
