import pytest
from pathlib import Path
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

from utils import is_openapi_schema, load_specs, list_files_in_api_specs



# TESTS ----------------------------------------------------------
# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))


@pytest.mark.parametrize("spec_file_path",
                        list_files_in_api_specs("*.json") +
                        list_files_in_api_specs("*.y*ml") )
def test_valid_openapi_specs(spec_file_path):
    spec_file_path = Path(spec_file_path)
    specs = load_specs(spec_file_path)
    if is_openapi_schema(specs):
        try:
            validate_spec(specs, spec_url=spec_file_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail("Failed validating {}:\n{}".format(spec_file_path, err.message))
