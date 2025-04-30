# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import urllib.parse
from pathlib import Path

from simcore_service_api_server.models.api_resources import (
    compose_resource_name,
    parse_collections_ids,
    parse_last_resource_id,
    parse_resources_ids,
    split_resource_name,
    split_resource_name_as_dict,
)


def test_parse_resource_id():
    resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
    parts = (
        "solvers",
        "simcore/services/comp/isolve",
        "releases",
        "1.3.4",
        "jobs",
        "f622946d-fd29-35b9-a193-abdd1095167c",
        "outputs",
        "output 22",
    )

    # cannot use this because cannot convert into URL? except {:path} in starlette ???
    assert str(Path(*parts)) == urllib.parse.unquote_plus(resource_name)

    assert compose_resource_name(*split_resource_name(resource_name)) == resource_name

    assert split_resource_name(resource_name) == parts
    assert compose_resource_name(*parts) == resource_name

    assert parse_last_resource_id(resource_name) == "output 22"

    assert (
        parse_last_resource_id(resource_name) == split_resource_name(resource_name)[-1]
    )

    collection_to_resource_id_map = split_resource_name_as_dict(resource_name)
    # Collection-ID -> Resource-ID
    assert tuple(collection_to_resource_id_map.keys()) == parse_collections_ids(
        resource_name
    )
    assert tuple(collection_to_resource_id_map.values()) == parse_resources_ids(
        resource_name
    )

    assert collection_to_resource_id_map["solvers"] == "simcore/services/comp/isolve"
    assert collection_to_resource_id_map["releases"] == "1.3.4"
    assert (
        collection_to_resource_id_map["jobs"] == "f622946d-fd29-35b9-a193-abdd1095167c"
    )
    assert collection_to_resource_id_map["outputs"] == "output 22"
