

import httpx
from typing import Optional

PRIMARY  = "https://api.binance.com"
FALLBACK = "https://api.binance.us"

# Stablecoins and leveraged tokens we don't want in the scanner
_STABLECOIN_BASES = {
    "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDP", "USTC",
    "GUSD", "SUSD", "FRAX", "PAXG", "EURT", "EUR", "GBP", "TRY",
}
_LEV_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


async def _fetch(path: str) -> dict | list:
    """Try PRIMARY, fall back to FALLBACK on any error."""
    errors = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for base in [PRIMARY, FALLBACK]:
            try:
                r = await client.get(base + path)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                errors.append(f"{base}: {e}")
    raise RuntimeError(f"Binance unreachable: {' | '.join(errors)}")


async def get_candles(symbol: str, interval: str, limit: int = 200) -> list[dict]:
    """Return normalised OHLCV candles, oldest first."""
    raw = await _fetch(f"/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}")
    return [
        {"time": k[0], "open": float(k[1]), "high": float(k[2]),
         "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
        for k in raw
    ]


async def get_ticker(symbol: str) -> dict:
    """Return 24h ticker for a single symbol."""
    raw = await _fetch(f"/api/v3/ticker/24hr?symbol={symbol}")
    return {
        "symbol":              raw["symbol"],
        "lastPrice":           float(raw["lastPrice"]),
        "priceChangePercent":  float(raw["priceChangePercent"]),
        "highPrice":           float(raw["highPrice"]),
        "lowPrice":            float(raw["lowPrice"]),
        "quoteVolume":         float(raw["quoteVolume"]),
    }


async def get_top_pairs(limit: int = 30) -> list[dict]:
    """Return the top liquid USDT pairs by 24h volume, filtered for quality."""
    raw = await _fetch("/api/v3/ticker/24hr")

    filtered = [
        t for t in raw
        if (
            t["symbol"].endswith("USDT")
            and not any(t["symbol"].endswith(s) for s in _LEV_SUFFIXES)
            and t["symbol"][:-4] not in _STABLECOIN_BASES
            and float(t.get("quoteVolume", 0)) >= 5_000_000
        )
    ]
    filtered.sort(key=lambda t: float(t["quoteVolume"]), reverse=True)

    return [
        {
            "symbol":    t["symbol"],
            "base":      t["symbol"][:-4],
            "lastPrice": float(t["lastPrice"]),
            "changePct": float(t["priceChangePercent"]),
            "volume":    float(t["quoteVolume"]),
        }
        for t in filtered[:limit]
    ]
