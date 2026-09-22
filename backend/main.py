
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────
# Checks whether the API is running and responding.
@app.get("/health")
def health():
    """Liveness probe — Azure App Service pings this to verify the app is running."""
    return {"status": "ok"}


# ── Scanner ───────────────────────────────────────────────────────────────────
# Scans the most liquid USDT pairs and generates a BUY, HOLD or SELL signal for each.
@app.get("/scan")
async def scan(interval: str = "4h", limit: int = Query(default=30, le=50)):

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
# Retrieves historical price data and calculates the SMA series and trading signal for the chart.
@app.get("/signal/{symbol}")
async def signal(symbol: str, interval: str = "4h"):

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


# ── AI Insight ───────────────────────────────────────────────────────────────
# Generates human-readable market commentary from the calculated signal and market data.
@app.get("/insight/{symbol}")
async def get_insight(symbol: str, interval: str = "4h"):

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
# Runs the SMA strategy against historical data and compares it with buy-and-hold performance.
@app.get("/backtest/{symbol}")
async def backtest(symbol: str, interval: str = "4h"):

    sym = symbol.upper() + ("USDT" if not symbol.upper().endswith("USDT") else "")
    try:
        candles = await binance.get_candles(sym, interval, limit=500)
        closes = [c["close"] for c in candles]
        result = analytics.run_backtest(closes)
        return {"symbol": sym, "interval": interval, **result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
