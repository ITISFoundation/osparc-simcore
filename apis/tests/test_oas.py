from pathlib import Path

import pytest
import yaml

from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError


def test_openapi_specs():
    parent_path = Path(__file__).parent.parent
    print("testing...")
    list_of_paths = parent_path.rglob("openapi.yaml")
    for spec_file_path in list_of_paths:
        print("testing ", str(spec_file_path))
        assert spec_file_path.exists()
        with spec_file_path.open() as file_ptr:
            openapi_specs = yaml.load(file_ptr)
            try:
                validate_spec(openapi_specs, spec_url=spec_file_path.as_uri())
            except OpenAPIValidationError as err:
                pytest.fail(err.message)
