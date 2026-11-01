"""Locate Wasabi coordinator logs and prison data in supported run layouts."""
import os


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


def find_wasabi_prison_file(base_path: str) -> str | None:
    # Prison.txt is stored relative to the coordinator log in every supported layout.
    log_file = find_wasabi_coordinator_log_file(base_path)
    if log_file is not None:
        prison_file = os.path.join(os.path.dirname(log_file), 'WabiSabi', 'Prison.txt')
        if os.path.isfile(prison_file):
            return prison_file
    return None
