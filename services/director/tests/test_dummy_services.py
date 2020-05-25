# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import pytest
import json
import logging
from helpers import json_schema_validator

log = logging.getLogger(__name__)


def test_services_conformity(configure_schemas_location, push_services):
    from simcore_service_director import resources

    services = push_services(1, 1)
    with resources.stream(resources.RESOURCE_NODE_SCHEMA) as file_pt:
        service_schema = json.load(file_pt)
    for service in services:
        # validate service
        json_schema_validator.validate_instance_object(
            service["service_description"], service_schema
        )
