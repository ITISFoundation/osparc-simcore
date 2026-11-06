# pylint: disable=redefined-outer-name

import logging

import pytest
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from simcore_service_director_v2.modules.director_v0 import _parse_running_services

_VALID_SERVICE: dict = {
    "service_key": "simcore/services/dynamic/raw-graphs",
    "service_version": "2.10.6",
    "user_id": 1,
    "project_id": "32fb4eb6-ab30-11ef-9ee4-0242ac140008",
    "service_uuid": "f1e2d3c4-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
    "service_basepath": "/x/f1e2d3c4-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
    "service_host": "raw-graphs_f1e2d3c4-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
    "service_port": 4000,
    "published_port": None,
    "entry_point": "",
    "service_state": "running",
    "service_message": "",
    "product_name": "osparc",
}

# A service started from the wrong image is incompatible with legacy mode:
# it publishes no port, so director-v0 reports service_port as null
_BROKEN_SERVICE: dict = {
    "service_key": "simcore/services/dynamic/parto-app",
    "service_version": "2.0.0",
    "user_id": 1,
    "project_id": "32fb4eb6-ab30-11ef-9ee4-0242ac140008",
    "service_uuid": "f4d53f47-9a96-4214-a14c-8a3096a1aeeb",
    "service_basepath": None,
    "service_host": "parto-app_f4d53f47-9a96-4214-a14c-8a3096a1aeeb",
    "service_port": None,
    "published_port": None,
    "entry_point": None,
    "service_state": "failed",
    "service_message": "task: non-zero exit (1)",
    "product_name": "s4l",
}


def test_parse_running_services_all_valid():
    assert _parse_running_services([_VALID_SERVICE]) == [RunningDynamicServiceDetails(**_VALID_SERVICE)]


def test_parse_running_services_skips_unparsable_entry_and_logs_error(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.ERROR)

    services = _parse_running_services([_VALID_SERVICE, _BROKEN_SERVICE])
    assert services == [RunningDynamicServiceDetails(**_VALID_SERVICE)]

    error_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_messages) == 1
    message = error_messages[0]
    assert "LEGACY mode" in message
    assert "paths-mapping" in message
    assert "docker service rm" in message
    # the log carries the raw entry so ops can identify and remove the service
    assert _BROKEN_SERVICE["service_uuid"] in message
    assert _BROKEN_SERVICE["service_host"] in message
