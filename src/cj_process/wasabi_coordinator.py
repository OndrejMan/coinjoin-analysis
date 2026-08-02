"""Locate Wasabi coordinator logs and prison data in supported run layouts."""
import os


def find_wasabi_coordinator_log_file(base_path: str) -> str:
    log_file = os.path.join(base_path, 'WalletWasabi', 'Backend', 'Logs.txt')
    if not os.path.exists(log_file):
        log_file = os.path.join(base_path, 'data', 'wasabi-backend', 'backend', 'Logs.txt')
    return log_file


def find_wasabi_prison_file(base_path: str) -> str:
    prison_file = os.path.join(base_path, 'WalletWasabi', 'Backend', 'WabiSabi', 'Prison.txt')
    if not os.path.exists(prison_file):
        prison_file = os.path.join(base_path, 'data', 'wasabi-backend', 'backend', 'WabiSabi', 'Prison.txt')
    return prison_file
