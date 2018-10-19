import sys
import json
from pathlib import Path

import yaml


def list_files_in_api_specs(wildcard):
    """ Helper function to parameterize tests with list of files

    e.g.  pytest -v  test_individual_openapi_schemas.py

    test_individual_openapi_schemas.py::test_valid_individual_openapi_schemas_specs[/home/crespo/devp/osparc-simcore/api/specs/shared/schemas/node-meta-v0.0.1.json] PASSED
    """
    here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    specs_dir = here.parent / "specs"

    # NOTE: keep as string and not path, so it can be rendered
    return list(str(p) for p in specs_dir.rglob(wildcard))


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
