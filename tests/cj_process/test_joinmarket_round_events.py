import json
from unittest import mock

import pytest

from cj_process.parse_cj_logs import (
    find_joinmarket_client_log_files,
    find_joinmarket_round_events_file,
    joinmarket_parse_round_events,
)


def test_joinmarket_round_events_parse_matched_txid(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events_file = data_dir / "joinmarket_round_events.json"
    events_file.write_text(
        json.dumps(
            [
                {
                    "round_id": 1,
                    "engine": "joinmarket",
                    "status": "stopped",
                    "taker": "jcs-000",
                    "candidate_makers": ["jcs-001", "jcs-002"],
                    "destination_address": "output-a0",
                    "txid": "txA",
                    "block_height": 7,
                }
            ]
        ),
        encoding="utf-8",
    )
    raw_tx_db = {
        "funding": {
            "txid": "funding",
            "vout": [
                {
                    "n": 0,
                    "value": 0.0015,
                    "scriptPubKey": {"address": "input-a"},
                }
            ],
        },
        "txA": {
            "txid": "txA",
            "mine_time": "2026-06-13 09:10:00.000",
            "vin": [{"txid": "funding", "vout": 0}],
            "vout": [
                {
                    "n": 0,
                    "value": 0.001,
                    "scriptPubKey": {"address": "output-a0"},
                },
                {
                    "n": 1,
                    "value": 0.0004,
                    "scriptPubKey": {"address": "output-a1"},
                },
            ],
        },
    }

    assert find_joinmarket_round_events_file(str(tmp_path)) == str(events_file)

    coinjoins, rounds = joinmarket_parse_round_events(str(tmp_path), raw_tx_db)

    assert list(coinjoins) == ["txA"]
    assert coinjoins["txA"]["round_id"] == "1"
    assert coinjoins["txA"]["broadcast_time"] == "2026-06-13 09:10:00.000"
    assert coinjoins["txA"]["joinmarket_round_event"]["taker"] == "jcs-000"
    assert rounds["1"]["round_start_timestamp"] == "2026-06-13 09:10:00.000"


def test_joinmarket_round_events_allow_empty_label_file(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events_file = data_dir / "joinmarket_round_events.json"
    events_file.write_text("[]", encoding="utf-8")

    coinjoins, rounds = joinmarket_parse_round_events(str(tmp_path), {})

    assert find_joinmarket_round_events_file(str(tmp_path)) == str(events_file)
    assert coinjoins == {}
    assert rounds == {}


def test_dropped_joinmarket_events_do_not_create_rounds(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events_file = data_dir / "joinmarket_round_events.json"
    events_file.write_text(
        json.dumps(
            [
                {"round_id": 1, "status": "failed", "txid": None},
                {
                    "round_id": 2,
                    "status": "confirmed",
                    "txid": "not-in-exported-blocks",
                    "timestamp": "2026-06-13 09:10:00.000",
                },
            ]
        ),
        encoding="utf-8",
    )

    with mock.patch('cj_process.parse_cj_logs.als.run_command') as run_command:
        coinjoins, rounds = joinmarket_parse_round_events(str(tmp_path), {})

    assert coinjoins == {}
    assert rounds == {}
    run_command.assert_not_called()


def test_empty_joinmarket_log_directory_is_not_usable(tmp_path):
    (tmp_path / 'data' / 'jcs-000' / 'joinmarket').mkdir(parents=True)

    assert find_joinmarket_client_log_files(str(tmp_path)) == []


def test_joinmarket_event_timestamp_is_normalized(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'joinmarket_round_events.json').write_text(
        json.dumps([{'round_id': 1, 'txid': 'txA', 'timestamp': '2026-01-01T12:34:56Z'}]),
        encoding='utf-8',
    )
    raw_tx_db = {'txA': {'txid': 'txA', 'vin': [], 'vout': []}}

    coinjoins, rounds = joinmarket_parse_round_events(str(tmp_path), raw_tx_db)

    assert coinjoins['txA']['broadcast_time'] == '2026-01-01 12:34:56.000'
    assert rounds['1']['round_start_timestamp'] == '2026-01-01 12:34:56.000'


def test_duplicate_round_id_with_different_txids_is_rejected(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events_file = data_dir / "joinmarket_round_events.json"
    events_file.write_text(
        json.dumps([
            {"round_id": 1, "status": "confirmed", "txid": "txA", "timestamp": "2026-01-01"},
            {"round_id": 1, "status": "confirmed", "txid": "txB", "timestamp": "2026-01-02"},
        ]),
        encoding="utf-8",
    )
    raw_tx_db = {
        txid: {
            "txid": txid,
            "vin": [],
            "vout": [],
        }
        for txid in ("txA", "txB")
    }

    with pytest.raises(ValueError, match="round ids map to multiple txids"):
        joinmarket_parse_round_events(str(tmp_path), raw_tx_db)


def test_duplicate_txid_with_different_round_ids_is_rejected(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events_file = data_dir / "joinmarket_round_events.json"
    events_file.write_text(
        json.dumps([
            {"round_id": 1, "status": "confirmed", "txid": "txA", "timestamp": "2026-01-01"},
            {"round_id": 2, "status": "confirmed", "txid": "txA", "timestamp": "2026-01-02"},
        ]),
        encoding="utf-8",
    )
    raw_tx_db = {
        "txA": {
            "txid": "txA",
            "vin": [],
            "vout": [],
        }
    }

    with pytest.raises(ValueError, match="txids map to multiple round ids"):
        joinmarket_parse_round_events(str(tmp_path), raw_tx_db)
