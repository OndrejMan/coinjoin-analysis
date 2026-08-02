from cj_process import parse_cj_logs
from utils import write_manifest


def test_wasabi_uses_sources_declared_by_manifest(tmp_path):
    first = tmp_path / 'data' / 'first' / 'Logs.txt'
    second = tmp_path / 'data' / 'second' / 'Logs.txt'
    for path in (first, second):
        path.parent.mkdir(parents=True)
        path.write_text('coordinator log\n', encoding='utf-8')
    write_manifest(tmp_path, first, additional_log_paths=(second,))
    assert parse_cj_logs.find_wasabi_coordinator_log_files(str(tmp_path)) == [str(first), str(second)]


def test_wasabi_source_selection_leaves_manifest_validation_to_pipeline(tmp_path):
    path = tmp_path / 'data' / 'coordinator' / 'Logs.txt'
    path.parent.mkdir(parents=True)
    path.write_text('coordinator log\n', encoding='utf-8')
    write_manifest(tmp_path, path, complete=False, positive_count=99)
    path.write_text('modified coordinator log\n', encoding='utf-8')
    assert parse_cj_logs.find_wasabi_coordinator_log_files(str(tmp_path)) == [str(path)]
