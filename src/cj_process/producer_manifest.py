"""Read the source locations declared by an emulator export."""

import json
import os
from typing import Any


def load_producer_label_manifest(data_path: str) -> Any | None:
    manifest_path = os.path.join(data_path, 'coinjoin_label_manifest.json')
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path, 'r', encoding='utf-8') as manifest_file:
        return json.load(manifest_file)


def producer_label_manifest_engine(data_path):
    manifest = load_producer_label_manifest(data_path)
    return manifest.get('engine') if manifest is not None else None
