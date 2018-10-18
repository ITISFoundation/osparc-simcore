from pathlib import Path

import pytest
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

from utils import is_openapi_schema, read_schema

_API_DIR = Path(__file__).parent.parent

def validate_openapi_spec(list_of_paths):
    for spec_file_path in list_of_paths:
        specs = read_schema(spec_file_path)
        if is_openapi_schema(specs):
            try:
                validate_spec(specs, spec_url=spec_file_path.as_uri())
            except OpenAPIValidationError as err:
                pytest.fail("Error validating {file}:\n{error}".format(file=spec_file_path, error=err.message))

def test_valid_openapi_specs():
    # get all the openapi complete specs
    validate_openapi_spec(_API_DIR.rglob("*.json"))
    validate_openapi_spec(_API_DIR.rglob("*.yaml"))
    validate_openapi_spec(_API_DIR.rglob("*.yml"))
