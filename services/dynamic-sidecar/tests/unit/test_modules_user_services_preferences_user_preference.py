# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name

import pytest
from models_library.services import ServiceKey
from pydantic import parse_obj_as
from simcore_service_dynamic_sidecar.modules.user_services_preferences._user_preference import (
    get_model_class,
)


@pytest.fixture
def service_key() -> ServiceKey:
    return parse_obj_as(ServiceKey, "simcore/services/dynamic/test-service-34")


def test_get_model_class_only_defined_once(service_key: ServiceKey):
    for _ in range(10):
        get_model_class(service_key)
