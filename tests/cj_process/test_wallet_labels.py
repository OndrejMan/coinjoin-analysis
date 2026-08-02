from cj_process.parse_cj_logs import UNKNOWN_WALLET_STRING, count_wallet_records, wallet_label


def test_count_wallet_records_ignores_unattributed_records():
    records = {
        "0": {"wallet_name": "wallet-000"},
        "1": {"address": "unattributed-output"},
        "2": {"wallet_name": "wallet-001"},
    }

    assert count_wallet_records(records, "wallet-000") == 1
    assert count_wallet_records(records, "wallet-001") == 1
    assert count_wallet_records(records, "wallet-002") == 0


def test_count_wallet_records_never_matches_the_unknown_marker():
    records = {"0": {"address": "unattributed-output"}}

    assert count_wallet_records(records, UNKNOWN_WALLET_STRING) == 0


def test_wallet_label_falls_back_for_unattributed_records():
    assert wallet_label("wallet-000") == "wallet-000"
    assert wallet_label(None) == UNKNOWN_WALLET_STRING
    assert wallet_label("") == UNKNOWN_WALLET_STRING
