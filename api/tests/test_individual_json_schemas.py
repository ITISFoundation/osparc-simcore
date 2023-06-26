from pathlib import Path

import pytest
from jsonschema import SchemaError, ValidationError, validate
from utils import is_json_schema, list_files_in_api_specs, load_specs


# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))
@pytest.mark.skip(reason="Implementing in PR 324")
@pytest.mark.parametrize(
    "spec_file_path",
    list_files_in_api_specs("*.json") + list_files_in_api_specs("*.y*ml"),
)
def test_valid_individual_json_schemas_specs(spec_file_path: Path):
    specs_dict = load_specs(spec_file_path)

    if is_json_schema(specs_dict):
        # it seems it is a json schema file
        try:
            dummy_instance = {}
            validate(dummy_instance, specs_dict)
        except SchemaError as err:
            # this is not good
            pytest.fail(f"Failed validating {spec_file_path}: \n {err.message} ")
        except ValidationError:
            # this is good
            return
        else:
            # this is also not good and bad from the validator...
            pytest.fail(
                f"Expecting an instance validation error if the schema in {spec_file_path} was correct"
            )
