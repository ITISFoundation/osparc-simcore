# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import urllib.parse
from pathlib import Path

from simcore_service_comp_resource_manager.models.api_resources import (
    compose_resource_name,
    parse_last_resource_id,
    split_resource_name,
)


def test_parse_resource_id():
    resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
    parts = [
        "solvers",
        "simcore/services/comp/isolve",
        "releases",
        "1.3.4",
        "jobs",
        "f622946d-fd29-35b9-a193-abdd1095167c",
        "outputs",
        "output 22",
    ]

    # cannot use this because cannot convert into URL? except {:path} in starlette ???
    assert str(Path(*parts)) == urllib.parse.unquote_plus(resource_name)

    assert compose_resource_name(*split_resource_name(resource_name)) == resource_name

    assert split_resource_name(resource_name) == parts
    assert compose_resource_name(*parts) == resource_name

    assert parse_last_resource_id(resource_name) == "output 22"

    assert (
        parse_last_resource_id(resource_name) == split_resource_name(resource_name)[-1]
    )
