from unittest import mock

import pytest

from cj_process import parse_cj_logs
from utils import write_manifest


def test_manifest_hash_mismatch_is_rejected(tmp_path):
    log_path = tmp_path / "data" / "wasabi-coordinator" / "coordinator" / "Logs.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("original coordinator log\n", encoding="utf-8")
    write_manifest(tmp_path, log_path)
    log_path.write_text("modified coordinator log\n", encoding="utf-8")

    with pytest.raises(ValueError, match="(size|hash) does not match manifest"):
        parse_cj_logs.find_wasabi_coordinator_log_files(str(tmp_path))


def test_incomplete_manifest_is_rejected_without_legacy_fallback(tmp_path):
    log_path = tmp_path / "data" / "wasabi-coordinator" / "coordinator" / "Logs.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("coordinator log\n", encoding="utf-8")
    write_manifest(tmp_path, log_path, complete=False)

    with pytest.raises(ValueError, match="manifest is incomplete"):
        parse_cj_logs.find_wasabi_coordinator_log_files(str(tmp_path))


def write_legacy_prison(tmp_path, prison_rows):
    log_path = tmp_path / "data" / "wasabi-backend" / "backend" / "Logs.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("coordinator log\n", encoding="utf-8")
    prison_path = log_path.parent / "WabiSabi" / "Prison.txt"
    prison_path.parent.mkdir()
    prison_path.write_text("".join(f"{row}\n" for row in prison_rows), encoding="utf-8")
    return prison_path


def test_load_prison_data_creates_records_for_rounds_without_coinjoin(tmp_path):
    round_id = "a" * 64
    utxo = f"{'b' * 64}-0"
    write_legacy_prison(tmp_path, [f"1700000000,{utxo},RoundDisruption,100000,{round_id},DoubleSpent"])

    # Prison entries exist precisely when rounds failed, so 'rounds' holds only the
    # placeholder written for experiments without a single completed CoinJoin.
    cjtx_stats = parse_cj_logs.load_prison_data({"rounds": {"no_round": []}}, str(tmp_path))

    assert cjtx_stats["rounds"]["no_round"] == []
    prison_logs = cjtx_stats["rounds"][round_id]["logs"]
    assert len(prison_logs) == 1
    assert prison_logs[0]["type"] == parse_cj_logs.CJ_LOG_TYPES.UTXO_IN_PRISON.name
    assert prison_logs[0]["utxo"] == utxo
    assert prison_logs[0]["adv_reason"] == "DoubleSpent"


def test_load_prison_data_keeps_logs_of_already_parsed_round(tmp_path):
    round_id = "a" * 64
    write_legacy_prison(tmp_path, [f"1700000000,{'b' * 64}-0,Cheating,{round_id}"])

    cjtx_stats = parse_cj_logs.load_prison_data(
        {"rounds": {round_id: {"logs": [{"type": "ROUND_STARTED"}]}}},
        str(tmp_path),
    )

    assert [entry["type"] for entry in cjtx_stats["rounds"][round_id]["logs"]] == [
        "ROUND_STARTED",
        parse_cj_logs.CJ_LOG_TYPES.UTXO_IN_PRISON.name,
    ]


def test_parse_backend_coinjoin_logs_returns_empty_for_incomplete_round(tmp_path):
    log_path = tmp_path / "Logs.txt"
    round_id = "a" * 64
    log_path.write_text(
        "2026-01-01 00:00:00.000 [1] INFO Arena.CreateRound (1) "
        f"Round ({round_id}): Created round with parameters: "
        "MaxSuggestedAmount:'1.0' BTC.\n",
        encoding="utf-8",
    )

    assert parse_cj_logs.parse_backend_coinjoin_logs(str(log_path), {}) == {}


def test_parse_backend_coinjoin_logs_parses_complete_round(tmp_path):
    log_path = tmp_path / "Logs.txt"
    round_id = "a" * 64
    txid = "b" * 64
    log_path.write_text(
        "2026-01-01 00:00:00.000 [1] INFO Arena.CreateRound (1) "
        f"Round ({round_id}): Created round with parameters: "
        "MaxSuggestedAmount:'1.0' BTC.\n"
        "2026-01-01 00:01:00.000 [1] INFO Arena.StepTransactionSigningPhaseAsync (1) "
        f"Round ({round_id}): Successfully broadcast the coinjoin: {txid}.\n",
        encoding="utf-8",
    )
    transaction = {"inputs": {}, "outputs": {}}

    with mock.patch.object(parse_cj_logs, "extract_tx_info", return_value=transaction) as extract_tx_info:
        result = parse_cj_logs.parse_backend_coinjoin_logs(str(log_path), {})

    extract_tx_info.assert_called_once_with(txid, {})
    assert result == {
        txid: {
            "inputs": {},
            "outputs": {},
            "round_id": round_id,
            "round_start_time": "2026-01-01 00:00:00.000",
            "broadcast_time": "2026-01-01 00:01:00.000",
            "is_blame_round": False,
            "is_cjtx": True,
        }
    }
