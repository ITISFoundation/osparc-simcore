import pytest
import json
import logging
from jsonschema import (validate, ValidationError)
from simcore_service_director import resources

log = logging.getLogger(__name__)

def test_v0_services_nonconformity(push_v0_schema_services):
    services = push_v0_schema_services(1,1)
    with resources.stream(resources.RESOURCE_NODE_SCHEMA) as file_pt:
        service_schema = json.load(file_pt)
    for service in services:
        # validate service
        with pytest.raises(ValidationError, message="expecting json schema validation error"):
            validate(service["service_description"], service_schema)

def test_v1_services_nonconformity(push_services):
    services = push_services(1,1)
    with resources.stream(resources.RESOURCE_NODE_SCHEMA) as file_pt:
        service_schema = json.load(file_pt)
    for service in services:
        # validate service
        validate(service["service_description"], service_schema)
