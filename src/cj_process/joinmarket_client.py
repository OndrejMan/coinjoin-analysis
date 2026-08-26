"""Locate the JoinMarket artifacts of a run and parse the CoinJoins they describe.

CoinJoin transaction IDs come from the exported jcs-*/joinmarket/jmwalletd.log
files.

``parse_cj_logs`` is imported lazily inside the functions that need it: it
imports this module at module level, and the references (extract_tx_info,
SM) must be resolved at call time so tests can patch
``parse_cj_logs`` attributes.
"""
import glob
import json
import logging
import os
import re

import cj_process.cj_analysis as als

logger = logging.getLogger(__name__)


def find_joinmarket_round_events_file(base_path: str):
    """Recognize JoinMarket exports by the presence of their round-event file."""
    candidate_paths = [
        os.path.join(base_path, 'data', 'joinmarket_round_events.json'),
        os.path.join(base_path, 'joinmarket_round_events.json'),
    ]
    for candidate_path in candidate_paths:
        if os.path.isfile(candidate_path):
            return candidate_path
    return None


def _find_joinmarket_log_files(wallet_path: str, *, include_wallet_logs=False):
    """Find console logs and optionally the wallet's per-nick log files."""
    log_patterns = [os.path.join(wallet_path, 'joinmarket', 'jmwalletd.log')]
    if include_wallet_logs:
        log_patterns.append(os.path.join(wallet_path, 'joinmarket', '.joinmarket', 'logs', '*.log'))
        # Current emulator exports the JoinMarket daemon's per-nick log files
        # directly here (for example ``logs/J58aUMAqe8RpvJxA.log``).
        log_patterns.append(os.path.join(wallet_path, 'logs', '*.log'))
    return [
        path for pattern in log_patterns for path in sorted(glob.glob(pattern))
        if os.path.isfile(path)
    ]


def find_joinmarket_client_log_files(base_path: str):
    return _find_joinmarket_log_files(os.path.join(base_path, 'data', 'jcs-*'))


# A derivation path next to an address is proof of ownership: a JoinMarket wallet
# never knows the path of a counterparty's address, so peer addresses logged during
# a round (for example in 'Makers responded with') are not matched here.
JOINMARKET_OWN_ADDRESS_PATTERN = re.compile(
    r"path:\s*(?P<path>m/[0-9']+[0-9'/]*)\s*,\s*address:\s*(?P<address>\w+)"
)
# Makers emit these two addresses after a successful round.  Unlike the full
# transaction dump and the ``Makers responded with`` line, this message is written
# by the wallet that controls both outputs, so it is safe ownership evidence.
JOINMARKET_MAKER_OUTPUTS_PATTERN = re.compile(
    r"mycjaddr,\s*mychange\s*=\s*(?P<cjaddr>\w+)\s*,\s*(?P<change>\w+)"
)


def joinmarket_wallet_addresses(wallet_path: str):
    """Collect the addresses a single JoinMarket wallet derived for itself.

    JoinMarket's key export and UTXO history can be incomplete when a final round
    is still unconfirmed or its outputs were already spent.  Ownership is therefore
    recovered from the structured coin exports and from the wallet's own logs.  In
    particular, maker ``mycjaddr, mychange`` records are authoritative for the two
    outputs the maker creates in a successful round.

    :param wallet_path: path of one jcs-* client directory
    :return: mapping {address: {'address': ..., 'path': ...}}, matching the shape
        that the keys.json branch of obtain_wallets_info builds
    """
    addresses = {}

    unspent_file = os.path.join(wallet_path, 'unspent_coins.json')
    if os.path.isfile(unspent_file):
        unspent_coins = []
        with open(unspent_file, 'r') as file:
            unspent_coins = json.load(file)
        if isinstance(unspent_coins, dict):
            unspent_coins = unspent_coins.get('utxos') or []
        if isinstance(unspent_coins, list):
            for utxo in unspent_coins:
                if not isinstance(utxo, dict):
                    continue
                address = utxo.get('address')
                if address:
                    addresses.setdefault(address, {'address': address, 'path': utxo.get('path')})

    log_files = _find_joinmarket_log_files(wallet_path, include_wallet_logs=True)
    if not log_files:
        logger.warning(
            'No JoinMarket log files found under %s; ownership can only be recovered '
            'from unspent coins, so coins this wallet already spent stay unattributed',
            wallet_path,
        )

    for log_file in log_files:
        with open(log_file, 'r', errors='replace') as file:
            log_text = file.read()
        for match in JOINMARKET_OWN_ADDRESS_PATTERN.finditer(log_text):
            address = match.group('address')
            addresses.setdefault(address, {'address': address, 'path': match.group('path')})
        for match in JOINMARKET_MAKER_OUTPUTS_PATTERN.finditer(log_text):
            for address in (match.group('cjaddr'), match.group('change')):
                addresses.setdefault(address, {'address': address})

    if not addresses:
        logger.warning('No JoinMarket wallet addresses recovered from %s', wallet_path)
    return addresses


def joinmarket_parse_coinjoin_logs(base_path: str, raw_tx_db: dict = {}, allow_rpc: bool = True):
    """
    Obtain information about coinjoins from collated logs from all separate clients
    :param base_path: base path where docker client images are stored
    :param raw_tx_db: database of all transaction loaded from btc-node
    :return: cjtx_stats structure with information about all detected coinjoins
    """
    # Resolved at call time so tests can patch ``parse_cj_logs`` attributes; see module docstring.
    from cj_process import parse_cj_logs

    print(f'Parsing coinjoin-relevant data from JoinMarket client logs {base_path}...', end='')
    # 1. Parse logs for each client separately
    # 2. Collate client logs into complete view

    success_coinjoins = {}
    for log_file in find_joinmarket_client_log_files(base_path):
        success_coinjoins[log_file] = als.joinmarket_find_coinjoins(log_file)

    all_coinjoins_duplicities = [success_coinjoins[path][txid] for path in success_coinjoins.keys() for txid in success_coinjoins[path].keys()]
    all_coinjoins = {txid: success_coinjoins[path][txid] for path in success_coinjoins.keys() for txid in success_coinjoins[path].keys()}

    parse_cj_logs.SM.print(
        f'Total JoinMarket coinjoins detected (with duplicities: {len(all_coinjoins_duplicities)})'
    )
    parse_cj_logs.SM.print(f'Total fully finished JoinMarket coinjoins found: {len(all_coinjoins)}')
    print('Parsing separate coinjoin transactions ', end='')
    cjtx_stats = {}
    for cjtxid in all_coinjoins.keys():
        # extract input and output addresses
        tx_record = parse_cj_logs.extract_tx_info(cjtxid, raw_tx_db, allow_rpc=allow_rpc)
        if tx_record is not None:
            tx_record['round_id'] = cjtxid
            tx_record['round_start_time'] = all_coinjoins[cjtxid]['timestamp']  # BUGBUG: bad round start time, needs to be extracted from logs better
            tx_record['broadcast_time'] = all_coinjoins[cjtxid]['timestamp']
            tx_record['is_blame_round'] = False
            tx_record['is_cjtx'] = True
            cjtx_stats[cjtxid] = tx_record
        else:
            logger.warning('Could not decode JoinMarket CoinJoin transaction tx=%s', cjtxid)
        print('.', end='')
    print('done')

    parse_cj_logs.SM.print(f'Total fully finished JoinMarket coinjoins processed: {len(cjtx_stats)}')

    return cjtx_stats
