from cj_process.cj_analysis import btc_to_sats


def test_btc_to_sats_preserves_exact_satoshi_value() -> None:
    assert btc_to_sats(0.00012738) == 12_738


def test_btc_to_sats_accepts_json_decimal_text() -> None:
    assert btc_to_sats("0.00012738") == 12_738
