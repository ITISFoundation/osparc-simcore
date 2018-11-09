import pytest
import yaml
from openapi_spec_validator import validate_spec  # , openapi_v3_spec_validator
from openapi_spec_validator.exceptions import OpenAPIValidationError


from pathlib import Path


API_VERSIONS = ("v0", )

@pytest.fixture(params=API_VERSIONS)
def openapi_from_path(request, api_specs_dir) -> Path:
    api_version = request.param
    specs_path = api_specs_dir / api_version / "openapi.yaml"
    assert specs_path.exits()
    return specs_path
