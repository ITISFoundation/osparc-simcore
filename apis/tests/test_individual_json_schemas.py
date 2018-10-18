import json
import yaml
from pathlib import Path

import pytest
from jsonschema import (
    SchemaError, 
    ValidationError, 
    validate)

_API_DIR = Path(__file__).parent.parent

def read_schema(spec_file_path: Path) -> dict:
    assert spec_file_path.exists()
    with spec_file_path.open() as file_ptr:
        if ".json" in  spec_file_path.suffix:
            schema_specs = json.load(file_ptr)
        else:
            schema_specs = yaml.load(file_ptr)
        return schema_specs

def validate_individual_schemas(list_of_paths):
    for spec_file_path in list_of_paths:
        specs_dict = read_schema(spec_file_path)
        if "$schema" in specs_dict:
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
