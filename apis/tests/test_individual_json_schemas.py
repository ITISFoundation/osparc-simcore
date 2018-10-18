from pathlib import Path

import pytest
from jsonschema import SchemaError, ValidationError, validate

from utils import read_schema, is_json_schema

_API_DIR = Path(__file__).parent.parent

def validate_individual_schemas(list_of_paths):
    for spec_file_path in list_of_paths:
        specs_dict = read_schema(spec_file_path)
        if is_json_schema(specs_dict):
            # it seems it is a json schema file
            try:
                dummy_instance = {}
                validate(dummy_instance, specs_dict)
            except SchemaError as err:
                # this is not good
                pytest.fail(err.message)            
            except ValidationError:
                # this is good
                continue
            else:
                # this is also not good and bad from the validator...
                pytest.fail("Expecting an instance validation error if the schema in {file} was correct".format(file=spec_file_path))            

def test_valid_individual_json_schemas_specs():
    validate_individual_schemas(_API_DIR.rglob("*.json"))
    validate_individual_schemas(_API_DIR.rglob("*.yaml"))
    validate_individual_schemas(_API_DIR.rglob("*.yml"))
