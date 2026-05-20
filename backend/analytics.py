
from typing import Optional


def sma(values: list[float], period: int) -> list[Optional[float]]:
    """
    Simple Moving Average. Returns None for positions before the first full window.
    O(n) — sliding window sum avoids recomputing from scratch each step.
    """
    result: list[Optional[float]] = []
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= period:
            total -= values[i - period]
        result.append(total / period if i >= period - 1 else None)
    return result


def compute_signal(closes: list[float]) -> dict:
    """
    Compute the BUY / SELL / HOLD signal from a list of closing prices.

    Returns a dict with:
      signal  — "BUY", "SELL", or "HOLD"
      price   — most recent close
      sma20   — current SMA20 value
      sma50   — current SMA50 value
      reason  — one-sentence human-readable explanation
    """
    MIN_CANDLES = 55  # need at least 50 for SMA50 plus a small buffer

    if not closes or len(closes) < MIN_CANDLES:
        return {
            "signal": "HOLD",
            "price":  closes[-1] if closes else None,
            "sma20":  None,
            "sma50":  None,
            "reason": "Insufficient historical data for analysis",
        }

    sma20_series = sma(closes, 20)
    sma50_series = sma(closes, 50)

    price = closes[-1]
    s20   = sma20_series[-1]
    s50   = sma50_series[-1]

    if price > s20 > s50:
        return {
            "signal": "BUY",
            "price": price, "sma20": s20, "sma50": s50,
            "reason": f"Price ({_fmt(price)}) > SMA20 ({_fmt(s20)}) > SMA50 ({_fmt(s50)}) — uptrend alignment",
        }
    if price < s20 < s50:
        return {
            "signal": "SELL",
            "price": price, "sma20": s20, "sma50": s50,
            "reason": f"Price ({_fmt(price)}) < SMA20 ({_fmt(s20)}) < SMA50 ({_fmt(s50)}) — downtrend alignment",
        }
    return {
        "signal": "HOLD",
        "price": price, "sma20": s20, "sma50": s50,
        "reason": "Moving averages not in clear alignment — consolidation or transition",
    }


def run_backtest(closes: list[float]) -> dict:
    """
    Walk-forward simulation of the SMA signal strategy.

    Rules:
      - Start with $100
      - Buy when signal flips to BUY, sell when it flips to SELL
      - 0.1% fee on each trade
      - No lookahead bias: signal at index i uses only closes[0..i]

    Returns final portfolio value, buy-and-hold value, trade log, and win rate.
    """
    FEE     = 0.001
    CAPITAL = 100.0

    cash        = CAPITAL
    units       = 0.0
    last_signal = None
    trades      = []
    START_IDX   = 55  # skip until we have enough data for SMA50

    for i in range(START_IDX, len(closes)):
        sig   = compute_signal(closes[: i + 1])
        price = closes[i]
        label = sig["signal"]

        if label == "BUY" and last_signal != "BUY" and cash > 0:
            fee   = cash * FEE
            units = (cash - fee) / price
            cash  = 0.0
            trades.append({"type": "BUY",  "price": price,
                           "portfolio": round(units * price, 2),
                           "sma20": sig["sma20"], "sma50": sig["sma50"]})
            last_signal = "BUY"

        elif label == "SELL" and last_signal != "SELL" and units > 0:
            gross = units * price
            fee   = gross * FEE
            cash  = gross - fee
            units = 0.0
            trades.append({"type": "SELL", "price": price,
                           "portfolio": round(cash, 2),
                           "sma20": sig["sma20"], "sma50": sig["sma50"]})
            last_signal = "SELL"

    final_price      = closes[-1]
    final_portfolio  = round(cash + units * final_price, 2)
    buy_and_hold     = round((CAPITAL / closes[START_IDX]) * final_price, 2)

    sells = [t for t in trades if t["type"] == "SELL"]
    buys  = [t for t in trades if t["type"] == "BUY"]
    wins  = sum(1 for s, b in zip(sells, buys) if s["portfolio"] > b["portfolio"])
    win_rate = round(wins / len(sells) * 100, 1) if sells else None

    return {
        "final_portfolio": final_portfolio,
        "buy_and_hold":    buy_and_hold,
        "outperformed":    final_portfolio > buy_and_hold,
        "total_trades":    len(trades),
        "win_rate":        win_rate,
        "trades":          trades,
    }


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if v >= 1000:
        return f"${v:,.2f}"
    if v >= 1:
        return f"${v:.4f}"
    return f"${v:.6f}"
