from pathlib import Path

import pytest

from cj_process.emulation_targets import (
    ANALYSIS_INPUT,
    DOCKER_DATA,
    EmulationTargetError,
    Requirement,
    collect_experiments,
    find_emulation_experiments,
)


def test_requirement_describes_directories_and_files():
    assert DOCKER_DATA.description == "<experiment>/data/"
    assert ANALYSIS_INPUT.description == "<experiment>/coinjoin_tx_info.json"


def test_requirement_distinguishes_files_from_directories(tmp_path):
    (tmp_path / "coinjoin_tx_info.json").mkdir()

    assert not ANALYSIS_INPUT.is_satisfied_by(tmp_path)
    assert not DOCKER_DATA.is_satisfied_by(tmp_path)


def test_find_emulation_experiments_is_sorted_and_skips_unrelated_folders(tmp_path):
    for name in ("experiment-2", "experiment-1"):
        (tmp_path / name / "data").mkdir(parents=True)
    (tmp_path / "notes").mkdir()
    (tmp_path / "readme.txt").write_text("", encoding="utf-8")

    assert find_emulation_experiments(tmp_path) == [
        tmp_path / "experiment-1",
        tmp_path / "experiment-2",
    ]


def test_collect_experiments_merges_several_target_paths(tmp_path):
    first = tmp_path / "run-a"
    second = tmp_path / "run-b"
    (first / "experiment-1" / "WalletWasabi").mkdir(parents=True)
    (second / "experiment-2" / "WalletWasabi").mkdir(parents=True)

    assert collect_experiments([str(first), str(second)]) == [
        first / "experiment-1",
        second / "experiment-2",
    ]


def test_collect_experiments_rejects_a_path_without_experiments(tmp_path):
    populated = tmp_path / "run-a"
    (populated / "experiment-1" / "data").mkdir(parents=True)
    empty = tmp_path / "run-b"
    empty.mkdir()

    with pytest.raises(EmulationTargetError) as exc_info:
        collect_experiments([str(populated), str(empty)])

    assert str(empty) in str(exc_info.value)


def test_find_emulation_experiments_reports_unreadable_paths(tmp_path):
    with pytest.raises(EmulationTargetError, match="Cannot inspect"):
        find_emulation_experiments(Path(tmp_path / "missing"))


def test_requirements_are_hashable_value_objects():
    assert Requirement("data") == DOCKER_DATA
    assert len({Requirement("data"), DOCKER_DATA}) == 1
