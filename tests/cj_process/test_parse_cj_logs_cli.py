import pytest

from cj_process.parse_cj_logs import get_experiments_base_paths, parse_arguments


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
    assert "<experiment>/WalletWasabi/" in error_output
    assert "<experiment>/coinjoin_tx_info.json" in error_output


def test_target_path_accepts_an_experiment_data_directory(tmp_path):
    (tmp_path / "experiment-1" / "data").mkdir(parents=True)

    arguments = parse_arguments(["--target-path", str(tmp_path)])

    assert arguments.target_path == [str(tmp_path)]


def test_collect_local_accepts_wallet_wasabi_experiment(tmp_path):
    (tmp_path / "experiment-1" / "WalletWasabi").mkdir(parents=True)

    arguments = parse_arguments(
        ["--action", "collect_local", "--target-path", str(tmp_path)]
    )

    assert arguments.target_path == [str(tmp_path)]


def test_analyze_only_does_not_require_exported_bitcoin_blocks(tmp_path):
    experiment = tmp_path / "experiment-1"
    experiment.mkdir()
    (experiment / "coinjoin_tx_info.json").write_text("{}", encoding="utf-8")

    arguments = parse_arguments(["--action", "analyze_only", "--target-path", str(tmp_path)])

    assert arguments.target_path == [str(tmp_path)]
    assert get_experiments_base_paths(str(tmp_path)) == [str(experiment)]


def test_experiment_paths_are_sorted_and_recognize_all_input_layouts(tmp_path):
    (tmp_path / "z-wallet" / "WalletWasabi").mkdir(parents=True)
    cached = tmp_path / "a-cached"
    cached.mkdir()
    (cached / "coinjoin_tx_info.json").write_text("{}", encoding="utf-8")
    (tmp_path / "m-docker" / "data").mkdir(parents=True)
    (tmp_path / "notes").mkdir()
    (tmp_path / "invalid" / "coinjoin_tx_info.json").mkdir(parents=True)

    assert get_experiments_base_paths(str(tmp_path)) == [
        str(cached),
        str(tmp_path / "m-docker"),
        str(tmp_path / "z-wallet"),
    ]


def test_experiment_paths_preserve_missing_path_diagnostic(tmp_path, capsys):
    missing = tmp_path / "missing"

    assert get_experiments_base_paths(str(missing)) == []
    assert str(missing) in capsys.readouterr().out
