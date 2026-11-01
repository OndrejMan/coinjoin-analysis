import argparse
from pathlib import Path


def validate_emulation_target(target_path: str) -> str:
    path = Path(target_path)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(
            f"EmuCoinJoin output path does not exist: {target_path}"
        )

    try:
        has_experiment = any(
            experiment.is_dir() and (experiment / "data").is_dir()
            for experiment in path.iterdir()
        )
    except OSError as exc:
        raise argparse.ArgumentTypeError(
            f"Cannot inspect EmuCoinJoin output path {target_path}: {exc}"
        ) from exc

    if not has_experiment:
        raise argparse.ArgumentTypeError(
            f"No EmuCoinJoin experiments found under {target_path}; "
            f"expected {target_path}/<experiment>/data/"
        )

    return target_path


