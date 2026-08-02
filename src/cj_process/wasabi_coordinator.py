"""Locate the Wasabi coordinator artifacts belonging to a run.

Discovery resolves which coordinator log files belong to a run, across the
layouts the analyzer supports, so callers work with resolved files instead of
hard-coded paths.
"""
import os
from pathlib import Path


def find_wasabi_exported_log_files(data_path):
    """Find Wasabi coordinator logs in legacy emulator exports.

    This fallback is used only when the run has no producer-label manifest.
    The emulator exports container directories as archives, so extraction may add
    intermediate directory levels below the known coordinator or backend root.

    Patterns are checked in order; logs from the first matching layout are used:

        <data_path>/wasabi-coordinator/coordinator/**/Logs.txt
        <data_path>/wasabi-backend/backend/**/Logs.txt
        <data_path>/wasabi-backend-2.6/backend/**/Logs.txt

    ``**`` matches zero or more nested directories. This accepts both the usual
    export layout and equivalent archive layouts with additional nesting, while
    preserving the preference for the Wasabi 2.6 coordinator log.
    """
    data_root = Path(data_path)
    if not data_root.is_dir():
        return []

    # Split Wasabi stores coordinator logs separately; legacy Wasabi keeps
    # them in the backend export. Prefer the coordinator when both exist.
    for directory_prefix in ('wasabi-coordinator', 'wasabi-backend'):
        export_roots = sorted(
            path
            for path in data_root.iterdir()
            if path.is_dir() and path.name.startswith(directory_prefix)
        )
        log_files = sorted(
            str(log_file.resolve())
            for export_root in export_roots
            for log_file in export_root.rglob('Logs.txt')
            if log_file.is_file()
        )
        if log_files:
            return log_files
    return []


def find_wasabi_coordinator_log_files(base_path):
    # Historical manual-Wasabi layout. This is checked first for an analysis
    # input assembled outside coinjoin-emulator; the emulator never writes here.
    local_log_file = os.path.join(base_path, 'WalletWasabi', 'Backend', 'Logs.txt')
    if os.path.isfile(local_log_file):
        return [local_log_file]

    # Emulator-export layout. Reached when the local layout above is absent:
    # EngineBase.store_logs() creates <base_path>/data and stores artifacts there.
    data_path = os.path.join(base_path, 'data')
    return find_wasabi_exported_log_files(data_path)


def find_wasabi_prison_file(base_path):
    # Prison.txt is stored relative to the coordinator log in every supported layout.
    for log_file in find_wasabi_coordinator_log_files(base_path):
        prison_file = os.path.join(os.path.dirname(log_file), 'WabiSabi', 'Prison.txt')
        if os.path.isfile(prison_file):
            return prison_file
    return None
