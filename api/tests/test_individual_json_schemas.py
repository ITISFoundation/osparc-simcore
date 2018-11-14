import pytest
from pathlib import Path
from jsonschema import SchemaError, ValidationError, validate

from utils import load_specs, is_json_schema, list_files_in_api_specs


# TESTS ----------------------------------------------------------
# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))
@pytest.mark.skip(reason="Implementing in PR 324")
@pytest.mark.parametrize("spec_file_path",
                        list_files_in_api_specs("*.json") +
                        list_files_in_api_specs("*.y*ml") )                        
def test_valid_individual_json_schemas_specs(spec_file_path):
    spec_file_path = Path(spec_file_path)
    specs_dict = load_specs(spec_file_path)

    if is_json_schema(specs_dict):
        # it seems it is a json schema file
        try:
            dummy_instance = {}
            validate(dummy_instance, specs_dict)
        except SchemaError as err:
            # this is not good
            pytest.fail("Failed validating %s: \n %s " % (spec_file_path, err.message))
        except ValidationError:
            # this is good
            return
        else:
            # this is also not good and bad from the validator...
            pytest.fail("Expecting an instance validation error if the schema in {file} was correct".format(file=spec_file_path))
