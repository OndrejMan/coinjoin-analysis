"""Locate and parse the Wasabi coordinator artifacts of a run."""
import os

from cj_process.producer_manifest import load_producer_label_manifest


def find_wasabi_coordinator_log_file(base_path: str) -> str | None:
    relative_paths = [
        'WalletWasabi/Backend/Logs.txt',
        'data/wasabi-coordinator/coordinator/Logs.txt',
        'data/wasabi-backend/backend/Logs.txt',
        'data/wasabi-backend-2.6/backend/Logs.txt',
    ]
    for relative_path in relative_paths:
        log_file = os.path.join(base_path, relative_path)
        if os.path.isfile(log_file):
            return log_file
    return None


def find_wasabi_coordinator_log_files(base_path):
    data_path = os.path.join(base_path, 'data')
    manifest = load_producer_label_manifest(data_path)
    if manifest is not None and manifest.get('engine') == 'wasabi':
        return [os.path.realpath(os.path.join(data_path, source['path'])) for source in manifest['sources']]
    log_file = find_wasabi_coordinator_log_file(base_path)
    return [log_file] if log_file is not None else []


def find_wasabi_prison_file(base_path: str) -> str | None:
    # Prison.txt is stored relative to the coordinator log in every supported layout.
    for log_file in find_wasabi_coordinator_log_files(base_path):
        prison_file = os.path.join(os.path.dirname(log_file), 'WabiSabi', 'Prison.txt')
        if os.path.isfile(prison_file):
            return prison_file
    return None


def parse_wasabi_coordinator_coinjoins(base_path, raw_txs):
    """Parse CoinJoins from the run's coordinator log sources."""
    from cj_process import parse_cj_logs

    log_files = find_wasabi_coordinator_log_files(base_path)
    if not log_files:
        raise FileNotFoundError(f'No Wasabi coordinator log found in {base_path}')
    coinjoins = {}
    for log_file in log_files:
        coinjoins.update(parse_cj_logs.parse_backend_coinjoin_logs(log_file, raw_txs))
    return coinjoins, log_files
