import json
from pathlib import Path

import pytest
from jsonschema import (
    SchemaError, 
    ValidationError, 
    validate)

from simcore_service_director import resources

API_VERSIONS = resources.listdir(resources.RESOURCE_OPENAPI_ROOT)

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

@pytest.mark.parametrize('version', API_VERSIONS)
def test_valid_individual_json_schemas_specs(version):
    name = "{root}/{version}/schemas".format(root=resources.RESOURCE_OPENAPI_ROOT, version=version)
    schemas_folder_path = resources.get_path(name)

    validate_individual_schemas(Path(schemas_folder_path).rglob("*.json"))
