from pathlib import Path

import pytest
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

from utils import is_json_schema, read_schema

_API_DIR = Path(__file__).parent.parent

_FAKE_OPEN_API_HEADERS = {
        "openapi": "3.0.0",
        "info":{
            "title": "An include file to define sortable attributes",
            "version": "1.0.0"
        },        
        "paths": {},
        "components": {
            "parameters":{},
            "schemas":{}
        }
    }

def correct_schema_local_references(schema_specs):
    for key, value in schema_specs.items():
        if isinstance(value, dict):
            correct_schema_local_references(value)
        elif "$ref" in key:
            if str(value).startswith("#/"):
                # correct the reference
                new_value = str(value).replace("#/", "#/components/schemas/")
                schema_specs[key] = new_value

def add_namespace_for_converted_schemas(schema_specs):
    # schemas converted from jsonschema do not have an overarching namespace.
    # the openapi validator does not like this
    # we use the jsonschema title to create a fake namespace
    fake_schema_specs = {
        "FakeName": schema_specs
        }
    return fake_schema_specs
    
def validate_individual_schemas(list_of_paths: list):
    for spec_file_path in list_of_paths:        
        # skip full specs
        if "openapi.yaml" in spec_file_path.name:
            continue
        # only consider schemas in a /schemas/ subfolder
        if "schemas" in str(spec_file_path):
            specs = read_schema(spec_file_path)
            if is_json_schema(specs):
                continue

            # correct local references
            correct_schema_local_references(specs)

            if str(spec_file_path).endswith("-converted.yaml"):
                # this is a json to openapi converted file
                specs = add_namespace_for_converted_schemas(specs)
            fake_openapi_headers = _FAKE_OPEN_API_HEADERS
            fake_openapi_headers["components"]["schemas"] = specs
            try:
                validate_spec(fake_openapi_headers, spec_url=spec_file_path.as_uri())
            except OpenAPIValidationError as err:
                pytest.fail(err.message)

def test_valid_individual_openapi_schemas_specs():
    validate_individual_schemas(_API_DIR.rglob("*.json"))
    validate_individual_schemas(_API_DIR.rglob("*.yaml"))
    validate_individual_schemas(_API_DIR.rglob("*.yml"))
