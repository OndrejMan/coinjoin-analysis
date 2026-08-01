import pytest

from cj_process.parse_cj_logs import parse_arguments


def test_target_path_must_exist(tmp_path, capsys):
    missing_path = tmp_path / "missing"

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(["--target-path", str(missing_path)])

    assert exc_info.value.code == 2
    assert "EmuCoinJoin output path does not exist" in capsys.readouterr().err


def test_target_path_must_contain_an_experiment(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(["--target-path", str(tmp_path)])

    error_output = capsys.readouterr().err
    assert exc_info.value.code == 2
    assert "expected" in error_output
    assert "<experiment>/data/" in error_output


def test_target_path_accepts_an_experiment_data_directory(tmp_path):
    (tmp_path / "experiment-1" / "data").mkdir(parents=True)

    arguments = parse_arguments(["--target-path", str(tmp_path)])

    assert arguments.target_path == [str(tmp_path)]
