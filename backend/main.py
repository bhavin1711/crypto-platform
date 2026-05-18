"""
main.py — FastAPI entry point
==============================
Owns three things: middleware setup, route definitions, and error handling.
Each route is thin — it delegates to a service module and returns the result.

Interview talking point:
  "I deliberately kept each route to 4-6 lines. The route's job is to
  parse the request and call the right service — not to do work itself.
  This makes the app easy to test: you can call analytics.compute_signal()
  directly without needing an HTTP client."

API surface:
  GET /health            → liveness probe (used by Azure App Service)
  GET /scan              → scanner: top pairs ranked by signal
  GET /signal/{symbol}   → chart data: candles + SMA series + signal
  GET /insight/{symbol}  → AI narrative for a single symbol
  GET /backtest/{symbol} → walk-forward simulation result
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import binance_service as binance
import analytics
import insight

app = FastAPI(
    title="Crypto Market Intelligence API",
    description="SMA-based signal engine with AI-assisted interpretation",
    version="1.0.0",
)

# CORS: allow all origins in development.
# In production, restrict to your Azure Static Web App URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness probe — Azure App Service pings this to verify the app is running."""
    return {"status": "ok"}


# ── Scanner ───────────────────────────────────────────────────────────────────

@app.get("/scan")
async def scan(interval: str = "4h", limit: int = Query(default=30, le=50)):
    """
    Returns the top `limit` liquid USDT pairs ranked by signal strength.
    Fetches candles for each pair and computes the SMA signal in parallel.

    Interview talking point:
      "In a production version this endpoint would read from a cache (Redis)
       that an ingestion job keeps warm. Right now it calls Binance directly,
       which is fine for an MVP but would hit rate limits at scale."
    """
    try:
        pairs = await binance.get_top_pairs(limit=limit)
        results = []
        for pair in pairs:
            try:
                candles = await binance.get_candles(pair["symbol"], interval, limit=100)
                closes = [c["close"] for c in candles]
                sig = analytics.compute_signal(closes)
                results.append({**pair, "signal": sig})
            except Exception:
                continue  # skip pairs that fail (e.g. newly listed, low liquidity)

        # sort: BUY first, then HOLD, then SELL
        order = {"BUY": 0, "HOLD": 1, "SELL": 2}
        results.sort(key=lambda r: order.get(r["signal"]["signal"], 1))
        return {"results": results, "interval": interval}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Signal (chart view) ───────────────────────────────────────────────────────

@app.get("/signal/{symbol}")
async def signal(symbol: str, interval: str = "4h"):
    """
    Returns the SMA signal + full price/SMA series for chart rendering.
    One call gives the frontend everything it needs to draw the chart.

    Interview talking point:
      "The frontend never does any math. It calls this endpoint and renders
       whatever comes back. That means the analytics logic has one home —
       analytics.py — and the frontend is a pure presentation layer."
    """
    sym = symbol.upper() + ("USDT" if not symbol.upper().endswith("USDT") else "")
    try:
        candles = await binance.get_candles(sym, interval, limit=200)
        closes = [c["close"] for c in candles]
        timestamps = [c["time"] for c in candles]

        sma20_series = analytics.sma(closes, 20)
        sma50_series = analytics.sma(closes, 50)
        sig = analytics.compute_signal(closes)

        return {
            "symbol": sym,
            "interval": interval,
            "signal": sig,
            "series": {
                "timestamps": timestamps,
                "closes": closes,
                "sma20": sma20_series,
                "sma50": sma50_series,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── AI Insight ────────────────────────────────────────────────────────────────

@app.get("/insight/{symbol}")
async def get_insight(symbol: str, interval: str = "4h"):
    """
    Generates analyst-style commentary for a symbol.
    Today: rule-based NLG. Future: OpenAI/Anthropic with same response shape.

    Interview talking point:
      "The insight module is the AI seam. The route just calls
       insight.generate() and returns the string. When I swap the
       implementation from rules to an LLM, this route never changes."
    """
    sym = symbol.upper() + ("USDT" if not symbol.upper().endswith("USDT") else "")
    try:
        candles = await binance.get_candles(sym, interval, limit=200)
        closes = [c["close"] for c in candles]
        ticker = await binance.get_ticker(sym)
        sig = analytics.compute_signal(closes)

        narrative = insight.generate(
            base=symbol.upper().replace("USDT", ""),
            timeframe=interval,
            price=sig["price"],
            change_24h=ticker.get("priceChangePercent", 0),
            signal=sig,
        )
        return {"symbol": sym, "narrative": narrative}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Backtest ──────────────────────────────────────────────────────────────────

@app.get("/backtest/{symbol}")
async def backtest(symbol: str, interval: str = "4h"):
    """
    Walk-forward simulation of the SMA signal strategy.
    Starts with $100, 0.1% fee per trade, compares vs buy-and-hold.

    Interview talking point:
      "Backtesting runs server-side so the frontend receives a compact
       result object — not 500 rows of candle data. The client stays thin."
    """
    sym = symbol.upper() + ("USDT" if not symbol.upper().endswith("USDT") else "")
    try:
        candles = await binance.get_candles(sym, interval, limit=500)
        closes = [c["close"] for c in candles]
        result = analytics.run_backtest(closes)
        return {"symbol": sym, "interval": interval, **result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
