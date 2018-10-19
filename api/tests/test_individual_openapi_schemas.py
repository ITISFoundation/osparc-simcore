from pathlib import Path

import pytest
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

from utils import is_json_schema, is_openapi_schema, read_schema, list_files_in_api_specs


# Conventions
_REQUIRED_FIELDS = ["error", "data"]
CONVERTED_SUFFIX = "-converted.yaml"

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
            ref = str(value)
            # FIXME: fails with circular links!
            # e.g. log.yml/#Error -> error.yml/#Log -> log.yaml/components/schemas/
            if ref.startswith("#/"):
                # correct the reference
                new_ref = ref.replace("#/", "#/components/schemas/")
                schema_specs[key] = new_ref

def add_namespace_for_converted_schemas(schema_specs):
    # schemas converted from jsonschema do not have an overarching namespace.
    # the openapi validator does not like this
    # we use the jsonschema title to create a fake namespace
    fake_schema_specs = {
        "FakeName": schema_specs
        }
    return fake_schema_specs

def validate_individual_schema(spec_file_path):
    # only consider schemas in a /schemas/ subfolder
    if "schemas" in str(spec_file_path):
        specs = read_schema(spec_file_path)
        if is_json_schema(specs):
            return

        if not is_openapi_schema(specs):
            # this is probably only part of a openapi specs
            # correct local references
            correct_schema_local_references(specs)
            if spec_file_path.name.endswith(CONVERTED_SUFFIX):
                # this is a json to openapi converted file
                specs = add_namespace_for_converted_schemas(specs)

            fake_openapi_headers = _FAKE_OPEN_API_HEADERS
            fake_openapi_headers["components"]["schemas"] = specs
            specs = fake_openapi_headers
        try:
            validate_spec(specs, spec_url=spec_file_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)


# TESTS ----------------------------------------------------------
# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))

@pytest.mark.parametrize("spec_file_path",
                        list_files_in_api_specs("*.json") +
                        list_files_in_api_specs("*.y*ml"))
def test_valid_individual_openapi_specs(spec_file_path):
    validate_individual_schema(Path(spec_file_path))
