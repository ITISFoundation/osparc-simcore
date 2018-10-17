from pathlib import Path

import pytest
import yaml

from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

from simcore_service_director import resources

API_VERSIONS = resources.listdir(resources.RESOURCE_OPENAPI_ROOT)

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
    
def validate_individual_schemas(list_of_paths):
    fake_openapi_headers = {
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
    
    for spec_file_path in list_of_paths:
        assert spec_file_path.exists()
        # only consider schemas
        if not "openapi.yaml" in str(spec_file_path.name) and "schemas" in str(spec_file_path):
            with spec_file_path.open() as file_ptr:
                schema_specs = yaml.load(file_ptr)
                # correct local references
                correct_schema_local_references(schema_specs)
                if str(spec_file_path).endswith("-converted.yaml"):
                    schema_specs = add_namespace_for_converted_schemas(schema_specs)
                fake_openapi_headers["components"]["schemas"] = schema_specs
            try:
                validate_spec(fake_openapi_headers, spec_url=spec_file_path.as_uri())
            except OpenAPIValidationError as err:
                pytest.fail(err.message)

@pytest.mark.parametrize('version', API_VERSIONS)
def test_valid_individual_openapi_schemas_specs(version):
    name = "{root}/{version}/schemas".format(root=resources.RESOURCE_OPENAPI_ROOT, version=version)
    schemas_folder_path = resources.get_path(name)
    validate_individual_schemas(Path(schemas_folder_path).rglob("*.yaml"))
    validate_individual_schemas(Path(schemas_folder_path).rglob("*.yml"))
