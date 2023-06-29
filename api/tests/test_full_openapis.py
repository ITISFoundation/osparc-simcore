from pathlib import Path

import pytest
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError
from utils import is_openapi_schema, list_files_in_api_specs, load_specs

# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))


@pytest.mark.parametrize(
    "spec_file_path",
    list_files_in_api_specs("*.json") + list_files_in_api_specs("*.y*ml"),
)
def test_valid_openapi_specs(spec_file_path: Path):
    specs = load_specs(spec_file_path)
    if is_openapi_schema(specs):
        try:
            validate_spec(specs, spec_url=spec_file_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(f"Failed validating {spec_file_path}:\n{err.message}")
