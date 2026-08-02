"""Tests for Wasabi producer-manifest verification."""

from cj_process import wasabi_manifest


def test_wasabi_manifest_compatibility_api_is_preserved(tmp_path):
    log_path = tmp_path / 'Logs.txt'
    log_path.write_text('coordinator log\n', encoding='utf-8')
    source = {
        'path': 'Logs.txt',
        'size_bytes': log_path.stat().st_size,
        'sha256': wasabi_manifest.sha256_file(log_path),
    }

    assert wasabi_manifest.PRODUCER_LABEL_MANIFEST_SCHEMA_VERSION == '1.0'
    assert wasabi_manifest.verify_wasabi_manifest_source(source, str(tmp_path)) == str(log_path)
