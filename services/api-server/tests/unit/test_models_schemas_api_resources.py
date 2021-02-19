# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import urllib.parse

from simcore_service_api_server.models.schemas._api_resources import (
    compose_resource_name,
    parse_resource_id,
    split_resource_name,
)


def test_parse_resource_id():
    resource_name = "/solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"

    assert parse_resource_id(resource_name) == "/output 22"

    assert parse_resource_id(resource_name) == split_resource_name(resource_name)[-1]

    assert compose_resource_name(split_resource_name(resource_name)) == resource_name
