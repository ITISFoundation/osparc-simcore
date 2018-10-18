import json
from pathlib import Path

import yaml


def read_schema(spec_file_path: Path) -> dict:
    assert spec_file_path.exists()
    with spec_file_path.open() as file_ptr:
        if ".json" in  spec_file_path.suffix:
            schema_specs = json.load(file_ptr)
        else:
            schema_specs = yaml.load(file_ptr)
        return schema_specs

def is_json_schema(specs: dict) -> bool:
    if "$schema" in specs:
        return True
    return False

def is_openapi_schema(specs: dict) -> bool:
    if "openapi" in specs:
        return True
    return False