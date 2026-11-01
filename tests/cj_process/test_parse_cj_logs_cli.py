import pytest

from cj_process import parse_cj_logs
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
    btc_node = tmp_path / "experiment-1" / "data" / "btc-node"
    btc_node.mkdir(parents=True)
    (btc_node / "block_0.json").write_text("{}", encoding="utf-8")

    arguments = parse_arguments(["--target-path", str(tmp_path)])

    assert arguments.target_path == [str(tmp_path)]


def test_collect_docker_requires_exported_bitcoin_blocks(tmp_path, capsys):
    (tmp_path / "experiment-1" / "data").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(["--action", "collect_docker", "--target-path", str(tmp_path)])

    assert exc_info.value.code == 2
    assert "collect_docker requires exported Bitcoin blocks" in capsys.readouterr().err


def test_collect_docker_accepts_exported_bitcoin_blocks_recursively(tmp_path):
    export_path = tmp_path / "experiment-1" / "data" / "btc-node" / "export"
    export_path.mkdir(parents=True)
    (export_path / "block_0.json").write_text("{}", encoding="utf-8")

    arguments = parse_arguments(
        ["--action", "collect_docker", "--target-path", str(tmp_path)]
    )

    assert arguments.target_path == [str(tmp_path)]


def test_collect_local_accepts_wallet_wasabi_experiment(tmp_path):
    (tmp_path / "experiment-1" / "WalletWasabi").mkdir(parents=True)

    arguments = parse_arguments(
        ["--action", "collect_local", "--target-path", str(tmp_path)]
    )

    assert arguments.target_path == [str(tmp_path)]


def test_analyze_only_requires_generated_coinjoin_info(tmp_path, capsys):
    (tmp_path / "experiment-1" / "data").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(["--action", "analyze_only", "--target-path", str(tmp_path)])

    assert exc_info.value.code == 2
    assert "analyze_only requires <experiment>/coinjoin_tx_info.json" in capsys.readouterr().err


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


@pytest.mark.parametrize("action,overrides,artifact", [
    ("collect_docker", "LOAD_TXINFO_FROM_FILE=True", "coinjoin_tx_info.json"),
    ("collect_local", "LOAD_TXINFO_FROM_FILE=True", "coinjoin_tx_info.json"),
    (None, "LOAD_TXINFO_FROM_FILE=True", "coinjoin_tx_info.json"),
    ("analyze_only", "LOAD_TXINFO_FROM_FILE=False;LOAD_TXINFO_FROM_DOCKER_FILES=True",
     "data/btc-node/export/block_0.json"),
    ("collect_docker", "LOAD_TXINFO_FROM_DOCKER_FILES=False", "WalletWasabi"),
    ("analyze_only", "LOAD_TXINFO_FROM_FILE=False;LOAD_TXINFO_FROM_DOCKER_FILES=False",
     "WalletWasabi"),
])
def test_input_requirements_follow_overridden_configuration(tmp_path, action, overrides, artifact):
    target = tmp_path / "experiment-1" / artifact
    if target.suffix == ".json":
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")
    else:
        target.mkdir(parents=True)
    arguments = ["--target-path", str(tmp_path), "--env_vars", overrides]
    if action is not None:
        arguments.extend(["--action", action])

    parsed = parse_arguments(arguments)

    assert parsed.target_path == [str(tmp_path)]


@pytest.mark.parametrize("action,overrides,artifact,expected", [
    ("collect_docker", "LOAD_TXINFO_FROM_FILE=True", "data/btc-node/block_0.json",
     "analyze_only requires <experiment>/coinjoin_tx_info.json"),
    ("analyze_only", "LOAD_TXINFO_FROM_FILE=False;LOAD_TXINFO_FROM_DOCKER_FILES=True",
     "coinjoin_tx_info.json", "collect_docker requires <experiment>/data/"),
    ("analyze_only", "LOAD_TXINFO_FROM_FILE=False;LOAD_TXINFO_FROM_DOCKER_FILES=False",
     "coinjoin_tx_info.json", "collect_local requires <experiment>/WalletWasabi/"),
])
def test_missing_artifacts_are_checked_for_overridden_mode(
    tmp_path, capsys, action, overrides, artifact, expected
):
    target = tmp_path / "experiment-1" / artifact
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        parse_arguments([
            "--action", action, "--target-path", str(tmp_path), "--env_vars", overrides,
        ])

    assert error.value.code == 2
    assert expected in capsys.readouterr().err


def test_main_uses_overridden_target_and_input_mode(tmp_path, monkeypatch):
    cached = tmp_path / "cached"
    experiment = cached / "experiment-1"
    experiment.mkdir(parents=True)
    (experiment / "coinjoin_tx_info.json").write_text("{}", encoding="utf-8")
    observations = []

    class ReadyToProcess(Exception):
        pass

    def capture_configuration(base_path, save_figs, num_threads):
        observations.append((base_path, parse_cj_logs.op.LOAD_TXINFO_FROM_FILE))
        raise ReadyToProcess

    monkeypatch.setattr(parse_cj_logs, "op", None, raising=False)
    monkeypatch.setattr(parse_cj_logs, "process_multiple_experiments", capture_configuration)
    with pytest.raises(ReadyToProcess):
        parse_cj_logs.main([
            "--action", "collect_docker", "--target-path", str(tmp_path / "missing"),
            "--env_vars", f"LOAD_TXINFO_FROM_FILE=True;target_path={[str(cached)]!r}",
        ])

    assert observations == [(str(cached), True)]


def test_target_supplied_only_by_env_vars_is_validated(tmp_path, capsys):
    missing = tmp_path / "missing"

    with pytest.raises(SystemExit) as error:
        parse_arguments(["--env_vars", f"target_path={[str(missing)]!r}"])

    assert error.value.code == 2
    assert "EmuCoinJoin output path does not exist" in capsys.readouterr().err
