from analytics import sma, compute_signal


def test_sma_calculation():
    prices = [1, 2, 3, 4, 5]

    result = sma(prices, 5)

    assert result == 3


def test_buy_signal():
    signal = compute_signal(
        price=110,
        sma20=100,
        sma50=90
    )

    assert signal == "BUY"
    