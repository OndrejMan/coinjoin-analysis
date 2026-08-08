"""Refuse to time coins when the run directory carries no fullnode block data."""
import json
import os

import pytest

from cj_process.parse_cj_logs import (
    MissingBlockDataError,
    load_tx_database_from_btccore,
    obtain_wallets_info,
)

TXID = 'b' * 64


def write_block(btc_node_dir, txid, block_time=1700000000):
    """Write one block export in the shape load_tx_database_from_btccore() reads."""
    os.makedirs(btc_node_dir, exist_ok=True)
    block = {'time': block_time, 'tx': [{'txid': txid, 'hash': 'block-hash'}]}
    with open(os.path.join(btc_node_dir, f'block_{txid[:8]}.json'), 'w') as file:
        json.dump(block, file)


def write_wallet(tmp_path, coins):
    """Lay out the docker-file wallet directory obtain_wallets_info() reads."""
    wallet_dir = tmp_path / 'data' / 'wasabi-client-000'
    wallet_dir.mkdir(parents=True)
    (wallet_dir / 'keys.json').write_text('[]')
    (wallet_dir / 'coins.json').write_text(json.dumps(coins))


def test_absent_btc_node_directory_names_the_path(tmp_path):
    missing = str(tmp_path / 'data' / 'btc-node')

    with pytest.raises(MissingBlockDataError) as excinfo:
        load_tx_database_from_btccore(missing)

    assert missing in str(excinfo.value)


def test_btc_node_directory_without_block_exports_is_rejected(tmp_path):
    btc_node = tmp_path / 'data' / 'btc-node'
    btc_node.mkdir(parents=True)
    (btc_node / 'debug.log').write_text('not a block export')

    with pytest.raises(MissingBlockDataError) as excinfo:
        load_tx_database_from_btccore(str(btc_node))

    assert 'block_*.json' in str(excinfo.value)


def test_present_block_exports_are_loaded(tmp_path):
    """The guard must not fire on a complete run."""
    btc_node = tmp_path / 'data' / 'btc-node'
    write_block(str(btc_node), TXID)

    tx_db = load_tx_database_from_btccore(str(btc_node))

    assert list(tx_db) == [TXID]
    assert tx_db[TXID]['mine_time'].startswith('2023-')


def test_coin_without_any_block_time_aborts_the_run(tmp_path):
    """A held coin with an empty transaction database is a broken run, not a quiet default."""
    write_wallet(tmp_path, [
        {'txid': TXID, 'index': 0, 'address': 'bcrt1qheld', 'amount': 1, 'anonymityScore': 1},
    ])

    with pytest.raises(MissingBlockDataError) as excinfo:
        obtain_wallets_info(str(tmp_path), False, True, {})

    message = str(excinfo.value)
    assert 'wallet-000' in message
    assert TXID in message
    assert os.path.join('data', 'btc-node') in message


def test_wallet_holding_no_coins_needs_no_block_time(tmp_path):
    """A coinless wallet never needs a synthetic time, so an empty database is fine."""
    write_wallet(tmp_path, [])

    wallets_info, wallets_coins = obtain_wallets_info(str(tmp_path), False, True, {})

    assert wallets_info['wallet-000'] == {}
    assert wallets_coins['wallet-000'] == []
