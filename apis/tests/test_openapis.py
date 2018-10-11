from pathlib import Path

import pytest
import yaml

from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

_API_DIR = Path(__file__).parent.parent

def validate_openapi_spec(list_of_paths):
    for spec_file_path in list_of_paths:
        assert spec_file_path.exists()
        with spec_file_path.open() as file_ptr:
            openapi_specs = yaml.load(file_ptr)
            try:
                validate_spec(openapi_specs, spec_url=spec_file_path.as_uri())
            except OpenAPIValidationError as err:
                pytest.fail(err.message)

def test_valid_openapi_specs():
    # get all the openapi complete specs
    validate_openapi_spec(_API_DIR.rglob("openapi.yaml"))
    validate_openapi_spec(_API_DIR.rglob("openapi.yml"))
    
