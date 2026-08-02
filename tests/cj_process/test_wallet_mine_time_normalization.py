import json
from unittest import mock

from cj_process import parse_cj_logs


def write_wallet_files(run_dir, coins):
    wallet_dir = run_dir / "data" / "wasabi-client-000"
    wallet_dir.mkdir(parents=True)
    (wallet_dir / "coins.json").write_text(json.dumps(coins), encoding="utf-8")
    (wallet_dir / "keys.json").write_text("[]", encoding="utf-8")


def load_wallet_coins(run_dir, all_tx_db):
    options = parse_cj_logs.EmulParseOptions()
    options.READ_ONLY_COINJOIN_TX_INFO = False
    with (
        mock.patch.object(parse_cj_logs, "op", options, create=True),
        mock.patch.object(parse_cj_logs.anonymity_score, "parse_wallet_coins", return_value=[]),
    ):
        return parse_cj_logs.obtain_wallets_info(
            str(run_dir),
            load_wallet_info_via_rpc=False,
            load_wallet_from_docker_files=True,
            all_tx_db=all_tx_db,
        )


def test_wallet_export_handles_empty_transaction_database(tmp_path):
    write_wallet_files(tmp_path, [{"txid": "missing", "spentBy": "also-missing"}])

    _, wallets_coins = load_wallet_coins(tmp_path, {})

    coin = wallets_coins["wallet-000"][0]
    assert coin["create_time"] == "1970-01-01 00:10:00.000"
    assert coin["destroy_time"] == "1970-01-01 00:10:00.000"


def test_wallet_export_normalizes_database_mine_times(tmp_path):
    write_wallet_files(tmp_path, [{"txid": "created", "spentBy": "spent"}])
    all_tx_db = {
        "created": {"hash": "created-block", "mine_time": 1780000000},
        "spent": {"hash": "spent-block", "mine_time": "2026-08-02T18:00:00Z"},
    }

    _, wallets_coins = load_wallet_coins(tmp_path, all_tx_db)

    coin = wallets_coins["wallet-000"][0]
    assert coin["create_time"] == parse_cj_logs.format_mine_time(1780000000)
    assert coin["destroy_time"] == "2026-08-02 18:00:00.000"
