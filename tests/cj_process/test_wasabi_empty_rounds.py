import hashlib
import json

import pytest

from cj_process import parse_cj_logs


def write_manifest(run_dir, log_path, positive_count=0, complete=True):
    data_dir = run_dir / "data"
    manifest = {
        "schema_version": "1.0",
        "engine": "wasabi",
        "complete": complete,
        "reason": None if complete else "coordinator log capture failed",
        "positive_count": positive_count,
        "sources": [{
            "path": log_path.relative_to(data_dir).as_posix(),
            "size_bytes": log_path.stat().st_size,
            "sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        }],
    }
    (data_dir / "coinjoin_label_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_manifest_hash_mismatch_is_rejected(tmp_path):
    log_path = tmp_path / "data" / "wasabi-coordinator" / "coordinator" / "Logs.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("original coordinator log\n", encoding="utf-8")
    write_manifest(tmp_path, log_path)
    log_path.write_text("modified coordinator log\n", encoding="utf-8")

    with pytest.raises(ValueError, match="(size|hash) does not match manifest"):
        parse_cj_logs.find_wasabi_coordinator_log_files(str(tmp_path))


def test_incomplete_manifest_is_rejected_without_legacy_fallback(tmp_path):
    log_path = tmp_path / "data" / "wasabi-coordinator" / "coordinator" / "Logs.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("coordinator log\n", encoding="utf-8")
    write_manifest(tmp_path, log_path, complete=False)

    with pytest.raises(ValueError, match="manifest is incomplete"):
        parse_cj_logs.find_wasabi_coordinator_log_files(str(tmp_path))
