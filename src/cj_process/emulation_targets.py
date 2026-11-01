"""Shared discovery of EmuCoinJoin experiment directories."""

import argparse
from dataclasses import dataclass
from pathlib import Path


class EmulationTargetError(ValueError):
    """Raised when a target path does not hold experiments usable for an action."""


@dataclass(frozen=True)
class Requirement:
    """One artifact an experiment must provide before an action can run."""

    path: str
    must_be_file: bool = False

    @property
    def description(self) -> str:
        """Path of the artifact relative to a single experiment folder."""
        if self.must_be_file:
            return f'<experiment>/{self.path}'
        return f'<experiment>/{self.path}/'

    def is_satisfied_by(self, experiment: Path) -> bool:
        target = experiment / self.path
        return target.is_file() if self.must_be_file else target.is_dir()


DOCKER_DATA = Requirement('data')
WALLET_WASABI = Requirement('WalletWasabi')
ANALYSIS_INPUT = Requirement('coinjoin_tx_info.json', must_be_file=True)

# Any of these makes a subfolder recognizable as an experiment.
EXPERIMENT_MARKERS = (DOCKER_DATA, WALLET_WASABI, ANALYSIS_INPUT)


def is_experiment(path: Path) -> bool:
    """Decide whether a folder holds an experiment recognized by any workflow."""
    return path.is_dir() and any(marker.is_satisfied_by(path) for marker in EXPERIMENT_MARKERS)


def find_emulation_experiments(path: Path):
    """List experiment folders directly under a single target path."""
    try:
        return sorted(experiment for experiment in path.iterdir() if is_experiment(experiment))
    except OSError as exc:
        raise EmulationTargetError(
            f'Cannot inspect EmuCoinJoin output path {path}: {exc}'
        ) from exc


def collect_experiments(target_paths):
    """Gather experiments from every target path, requiring each one to hold some."""
    experiments = []
    for target_path in target_paths:
        path = Path(target_path)
        if not path.is_dir():
            raise EmulationTargetError(
                f'EmuCoinJoin output path does not exist: {target_path}'
            )

        found = find_emulation_experiments(path)
        if not found:
            expected = ' or '.join(f'{target_path}/{marker.description}'
                                   for marker in EXPERIMENT_MARKERS)
            raise EmulationTargetError(
                f'No EmuCoinJoin experiments found under {target_path}; expected {expected}'
            )
        experiments.extend(found)

    return experiments


def validate_emulation_target(target_path: str) -> str:
    try:
        collect_experiments([target_path])
    except EmulationTargetError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return target_path
