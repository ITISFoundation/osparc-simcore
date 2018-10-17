import json
from pathlib import Path

import pytest
from jsonschema import (
    SchemaError, 
    ValidationError, 
    validate)

_API_DIR = Path(__file__).parent.parent

def validate_individual_schemas(list_of_paths):
    for spec_file_path in list_of_paths:
        assert spec_file_path.exists()
        with spec_file_path.open() as file_ptr:
            schema_specs = json.load(file_ptr)
            try:
                dummy_instance = {}
                with pytest.raises(ValidationError, message="Expected a Json schema validation error"):
                    validate(dummy_instance, schema_specs)
            except SchemaError as err:
                pytest.fail(err.message)

def test_valid_individual_json_schemas_specs():
    validate_individual_schemas(_API_DIR.rglob("*.json"))
