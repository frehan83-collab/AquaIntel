"""Diagnostic: probe the 5 FRED series used by feed_cost_engine._fetch_fred.

Replicates the engine's exact request (no custom headers), then retries with a
browser User-Agent to distinguish series-ID problems from rate-limiting/UA blocking.
"""
import asyncio

import httpx

FRED_SERIES = {
    "PSOYBUSDM": "soy",
    "PSOILUSDM": "rapeseed",
    "PWHEAMTUSDM": "wheat",
    "PFISHUSDM": "fishmeal",
    "PROILUSDM": "fish_oil",
}

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def parse_last_value(text):
    for line in reversed(text.strip().split("\n")):
        parts = line.split(",")
        if len(parts) == 2 and parts[1].strip() not in ("", "."):
            try:
                v = float(parts[1].strip())
                if v > 0:
                    return v
            except ValueError:
                continue
    return None


async def probe(client, sid, label):
    try:
        resp = await client.get(URL.format(sid=sid))
        body_len = len(resp.text) if resp.text else 0
        last_line = (resp.text or "").strip().split("\n")[-1].strip() if resp.text else ""
        val = parse_last_value(resp.text) if resp.status_code == 200 and body_len >= 50 else None
        engine_would = "LIVE" if (resp.status_code == 200 and body_len >= 50 and val) else "SKIP->default_estimate"
        print(f"{label:8} {sid:14} http={resp.status_code} bytes={body_len:7} value={val} engine={engine_would} last_line=[{last_line[:60]}]")
    except Exception as exc:
        print(f"{label:8} {sid:14} ERROR {type(exc).__name__}: {str(exc)[:100]}")


async def main():
    print("== Pass 1: engine-style request (no User-Agent) ==")
    async with httpx.AsyncClient(timeout=15) as client:
        await asyncio.gather(*(probe(client, sid, "no-UA") for sid in FRED_SERIES))

    print("\n== Pass 2: with browser User-Agent ==")
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
        await asyncio.gather(*(probe(client, sid, "browserUA") for sid in FRED_SERIES))


if __name__ == "__main__":
    asyncio.run(main())
