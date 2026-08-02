"""JoinMarket collection uses daemon logs, independently of producer round labels."""

import json
from unittest import mock

import pytest

from cj_process import parse_cj_logs

TXID = "a" * 64
LABEL_TXID = "b" * 64


def write_run(run_dir, *, log_content=None, manifest_complete=True):
    data = run_dir / "data"
    data.mkdir()
    (data / "joinmarket_round_events.json").write_text(
        json.dumps([{"round_id": 1, "txid": LABEL_TXID}]), encoding="utf-8",
    )
    if manifest_complete is not None:
        (data / "coinjoin_label_manifest.json").write_text(
            json.dumps({"engine": "joinmarket", "complete": manifest_complete}), encoding="utf-8",
        )
    if log_content is not None:
        log = data / "jcs-007/joinmarket/jmwalletd.log"
        log.parent.mkdir(parents=True)
        log.write_text(log_content, encoding="utf-8")


def collect(run_dir):
    options = parse_cj_logs.EmulParseOptions()
    for name, value in {
        "LOAD_TXINFO_FROM_FILE": False,
        "LOAD_TXINFO_FROM_DOCKER_FILES": True,
        "READ_ONLY_COINJOIN_TX_INFO": False,
        "ASSUME_COORDINATOR_WALLET": False,
        "PARSE_ERRORS": True,
        "LOAD_COMPUTED_TRANSACTION_INFO": False,
        "SAVE_ANALYTICS_TO_FILE": False,
        "GENERATE_COINJOIN_GRAPH_BLIND": False,
        "GENERATE_COINJOIN_GRAPH": False,
    }.items():
        setattr(options, name, value)
    transactions = {
        txid: {"txid": txid, "vin": [], "vout": [], "mine_time": "2026-11-01 12:00:01.000"}
        for txid in (TXID, LABEL_TXID)
    }
    with (
        mock.patch.object(parse_cj_logs, "op", options, create=True),
        mock.patch.object(parse_cj_logs, "load_tx_database_from_btccore", return_value=transactions),
        mock.patch.object(parse_cj_logs, "obtain_wallets_info", return_value=({}, {})),
        mock.patch.object(parse_cj_logs, "parse_wasabi_coordinator_coinjoins") as wasabi,
        mock.patch.object(parse_cj_logs, "parse_coinjoin_errors") as errors,
        mock.patch.object(parse_cj_logs, "load_prison_data") as prison,
        mock.patch.object(parse_cj_logs, "load_anonscore_data"),
        mock.patch.object(parse_cj_logs, "analyze_coinjoin_stats", return_value={}),
        mock.patch.object(parse_cj_logs.als, "remove_link_between_inputs_and_outputs"),
        mock.patch.object(parse_cj_logs.als, "compute_link_between_inputs_and_outputs"),
        mock.patch.object(parse_cj_logs.als, "analyze_input_out_liquidity") as liquidity,
    ):
        result = parse_cj_logs.process_experiment((str(run_dir), False))
    wasabi.assert_not_called()
    errors.assert_not_called()
    prison.assert_not_called()
    return result


@pytest.mark.parametrize("manifest_complete", [True, False, None])
def test_collection_reads_client_log_even_when_round_labels_disagree(tmp_path, manifest_complete):
    log = (
        "2026-11-01 12:00:00,000 [INFO]  obtained tx\n"
        + json.dumps({"txid": TXID}, indent=4) + "\n"
        "2026-11-01 12:00:00,001 [INFO]  transaction built\n"
    )
    write_run(tmp_path, log_content=log, manifest_complete=manifest_complete)

    result = collect(tmp_path)

    assert set(result["coinjoins"]) == {TXID}
    assert "joinmarket_round_event" not in result["coinjoins"][TXID]


@pytest.mark.parametrize("manifest_complete", [True, None])
def test_round_labels_cannot_replace_missing_client_logs(tmp_path, manifest_complete):
    write_run(tmp_path, manifest_complete=manifest_complete)

    with pytest.raises(ValueError, match="requires exported.*jmwalletd.log"):
        collect(tmp_path)


def test_no_coinjoins_in_client_log_does_not_fall_back_to_positive_round_labels(tmp_path):
    write_run(tmp_path, log_content="daemon started, no coinjoins\n")

    result = collect(tmp_path)

    assert result["coinjoins"] == {}


def test_damaged_client_log_does_not_fall_back_to_round_labels(tmp_path):
    write_run(tmp_path, log_content="2026-11-01 12:00:00,000 [INFO]  obtained tx\n{\n")

    with pytest.raises(ValueError, match="unterminated transaction json"):
        collect(tmp_path)
