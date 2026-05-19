from analytics import sma, compute_signal


def test_sma_calculation():
    prices = [1, 2, 3, 4, 5]

    result = sma(prices, 5)

    assert result[-1] == 3.0


def test_buy_signal():
    closes = list(range(1, 60))

    result = compute_signal(closes)

    assert result["signal"] == "BUY"
