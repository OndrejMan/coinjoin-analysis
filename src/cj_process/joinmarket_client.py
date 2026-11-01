"""Parse the JoinMarket client logs of a run into CoinJoin records.

``parse_cj_logs`` is imported lazily inside the function that needs it: it
imports this module at module level, and the references (extract_tx_info, SM)
must be resolved at call time so tests can patch ``parse_cj_logs`` attributes.
"""
import logging
import os

import cj_process.cj_analysis as als

logger = logging.getLogger(__name__)


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

    clients_paths = []
    exp_base_path = os.path.join(base_path, 'data')
    files = os.listdir(exp_base_path) if os.path.exists(exp_base_path) else logging.error(f'Path {exp_base_path} does not exist')
    for file in files:
        target_exp_base_path = os.path.join(exp_base_path, file)
        if os.path.isdir(target_exp_base_path):
            if os.path.exists(os.path.join(target_exp_base_path, 'joinmarket')):
                clients_paths.append(target_exp_base_path)

    success_coinjoins = {}
    for client_path in clients_paths:
        success_coinjoins[client_path] = als.joinmarket_find_coinjoins(os.path.join(client_path, 'joinmarket', 'jmwalletd.log'))

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
