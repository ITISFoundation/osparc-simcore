import json
import sys
from pathlib import Path

import yaml

# Conventions
CONVERTED_SUFFIX = "-converted.yaml"


def specs_folder():
    here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    return here.parent / "specs"


def list_files_in_api_specs(wildcard):
    """ Helper function to parameterize tests with list of files

    e.g.  pytest -v  test_individual_openapi_schemas.py

    test_individual_openapi_schemas.py::test_valid_individual_openapi_schemas_specs[/home/crespo/devp/osparc-simcore/api/specs/shared/schemas/node-meta-v0.0.1.json] PASSED
    """
    specs_dir = specs_folder()

    # NOTE: keep as string and not path, so it can be rendered
    return list(str(p) for p in specs_dir.rglob(wildcard))


def list_all_openapi():
    """ Lists str paths for all openapi.yaml in api/specs
    """
    return [ pathstr for pathstr in list_files_in_api_specs("openapi.y*ml")
                        if not pathstr.endswith(CONVERTED_SUFFIX) ]  # skip converted schemas


def load_specs(spec_file_path: Path) -> dict:
    assert spec_file_path.exists(), spec_file_path
    with spec_file_path.open() as file_ptr:
        if ".json" in  spec_file_path.suffix:
            schema_specs = json.load(file_ptr)
        else:
            schema_specs = yaml.load(file_ptr)
        return schema_specs


def dump_specs(specs: dict, specs_path: Path):
    dump_fun = json.dump if specs_path.name.endswith(".json") else yaml.dump
    with specs_path.open("wt") as f:
        dump_fun(specs, f)


def is_json_schema(specs: dict) -> bool:
    return "$schema" in specs


def is_openapi_schema(specs: dict) -> bool:
    return "openapi" in specs
