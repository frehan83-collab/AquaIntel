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


#: Norges Bank quotes these per **100** units, not per one (verified 2026-10-18:
#: DKK 142.13, SEK 95.33, ISK 7.80 for 100 units). Getting this wrong understates a
#: Danish or Icelandic cost by 100x, so the divisor lives in one place.
PER_100_UNITS: frozenset[str] = frozenset({"DKK", "SEK", "ISK"})

#: Currencies Norges Bank quotes that this platform converts.
NORGES_BANK_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "DKK", "SEK", "ISK", "CAD", "PLN"}
)

#: Documented USD constants for currencies with **no licensed daily source** on this
#: deployment. Used only when the conversion is unavoidable, and always reported as a
#: fallback (never silently): the Chilean peso has no Norges Bank quote and FRED's
#: H.10 table does not carry it.
DOCUMENTED_USD_FALLBACK: dict[str, float] = {
    "CLP": 0.00105,  # 1 CLP ≈ USD 0.00105 (documented in the competitiveness engine)
    "ISK": 0.0072,
    "CAD": 0.74,
    "GBP": 1.27,
    "DKK": 0.145,
    "NOK": 0.093,
}


async def rate_to_usd(currency: str = "USD", *, timeout: float = 8.0) -> dict:
    """USD per one unit of ``currency``, from a licensed source where one exists.

    Returns ``{"currency", "usd_per_unit", "observed_at", "source", "is_fallback",
    "fallback_reason"}``. Sources, in order:

    * ``USD`` — 1.0;
    * a Norges Bank quote when the currency is in :data:`NORGES_BANK_CURRENCIES`
      (divided by 100 for :data:`PER_100_UNITS`), converted through the official
      USD/NOK rate on the same observation date;
    * otherwise the documented constant in :data:`DOCUMENTED_USD_FALLBACK`, flagged
      ``is_fallback`` with the reason — never a silent number.

    The cross-currency quotes that used to come from Yahoo Finance's chart API are
    gone (WS-31b): Yahoo's terms forbid deriving income from its data.
    """
    code = (currency or "USD").strip().upper()
    result: dict = {
        "currency": code,
        "usd_per_unit": None,
        "observed_at": None,
        "source": SOURCE_NAME,
        "is_fallback": False,
        "fallback_reason": None,
    }
    if code == "USD":
        result["usd_per_unit"] = 1.0
        return result

    if code == "NOK":
        # NOK is the base of every Norges Bank quote: USD per NOK = 1 / (NOK per USD).
        usd = await nok_rate("USD", timeout=timeout)
        nok_per_usd = usd.get("nok_per_unit")
        if nok_per_usd and not usd.get("is_fallback"):
            result.update(
                {
                    "usd_per_unit": round(1.0 / float(nok_per_usd), 8),
                    "observed_at": usd.get("observed_at"),
                    "source": f"{SOURCE_NAME} (NOK via USD/NOK)",
                }
            )
            return result
        reason = usd.get("fallback_reason") or "the official USD/NOK rate was unavailable"
    elif code in NORGES_BANK_CURRENCIES:
        usd = await nok_rate("USD", timeout=timeout)
        nok_per_usd = usd.get("nok_per_unit")
        quote = await nok_rate(code, timeout=timeout)
        nok_per_unit = quote.get("nok_per_unit")
        if nok_per_usd and nok_per_unit and not usd.get("is_fallback"):
            per_unit = float(nok_per_unit) / 100.0 if code in PER_100_UNITS else float(nok_per_unit)
            result.update(
                {
                    "usd_per_unit": round(per_unit / float(nok_per_usd), 8),
                    "observed_at": quote.get("observed_at") or usd.get("observed_at"),
                    "source": f"{SOURCE_NAME} ({code}/NOK via USD/NOK)",
                    "is_fallback": bool(quote.get("is_fallback")),
                    "fallback_reason": quote.get("fallback_reason"),
                }
            )
            return result
        reason = (
            usd.get("fallback_reason")
            or quote.get("fallback_reason")
            or "the official USD/NOK or cross rate was unavailable"
        )
    else:
        reason = f"no licensed daily source for {code} on this deployment"

    constant = DOCUMENTED_USD_FALLBACK.get(code)
    result.update(
        {
            "usd_per_unit": constant,
            "is_fallback": True,
            # The source names what was actually used, not the feed that was missing.
            "source": f"documented constant ({code} to USD)",
            "fallback_reason": (
                reason
                + (f"; fell back to the documented constant {constant} USD per {code}"
                   if constant else "; no documented constant exists for this currency")
            ),
        }
    )
    log.warning("fx.rate_to_usd_fallback", currency=code, reason=reason)
    return result


def clear_cache() -> None:
    """Drop the memo (tests and an operator-triggered refresh)."""
    _cache.clear()
