# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
from aiohttp import web
from aioresponses import aioresponses as AioResponsesMock
from aioresponses.core import CallbackResult
from models_library.api_schemas_storage import FileMetaData
from models_library.clusters import Cluster
from models_library.projects_state import RunningState
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aioresponses_mocker",
]

# WARNING: any request done through the client will go through aioresponses. It is
# unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
# Other than that it seems to behave nicely
PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]


# The adjacency list is defined as a dictionary with the key to the node and its list of successors
FULL_PROJECT_PIPELINE_ADJACENCY: Dict[str, List[str]] = {
    "62bca361-8594-48c8-875e-b8577e868aec": [
        "e0d7a1a5-0700-42c7-b033-97f72ac4a5cd",
        "5284bb5b-b068-4d0e-9075-3d5d8eec5060",
        "750454a8-b450-43ce-a012-40b669f7d28c",
    ],
    "e0d7a1a5-0700-42c7-b033-97f72ac4a5cd": ["e83a359a-1efe-41d3-83aa-a285afbfaf12"],
    "5284bb5b-b068-4d0e-9075-3d5d8eec5060": ["e83a359a-1efe-41d3-83aa-a285afbfaf12"],
    "750454a8-b450-43ce-a012-40b669f7d28c": ["e83a359a-1efe-41d3-83aa-a285afbfaf12"],
    "e83a359a-1efe-41d3-83aa-a285afbfaf12": [],
}

FULL_PROJECT_NODE_STATES: Dict[str, Dict[str, Any]] = {
    "62bca361-8594-48c8-875e-b8577e868aec": {"modified": True, "dependencies": []},
    "e0d7a1a5-0700-42c7-b033-97f72ac4a5cd": {
        "modified": True,
        "dependencies": ["62bca361-8594-48c8-875e-b8577e868aec"],
    },
    "5284bb5b-b068-4d0e-9075-3d5d8eec5060": {
        "modified": True,
        "dependencies": ["62bca361-8594-48c8-875e-b8577e868aec"],
    },
    "750454a8-b450-43ce-a012-40b669f7d28c": {
        "modified": True,
        "dependencies": ["62bca361-8594-48c8-875e-b8577e868aec"],
    },
    "e83a359a-1efe-41d3-83aa-a285afbfaf12": {
        "modified": True,
        "dependencies": [
            "e0d7a1a5-0700-42c7-b033-97f72ac4a5cd",
            "5284bb5b-b068-4d0e-9075-3d5d8eec5060",
            "750454a8-b450-43ce-a012-40b669f7d28c",
        ],
    },
}


def create_computation_cb(url, **kwargs) -> CallbackResult:

    assert "json" in kwargs, f"missing body in call to {url}"
    body = kwargs["json"]
    for param in ["user_id", "project_id"]:
        assert param in body, f"{param} is missing from body: {body}"
    state = (
        RunningState.PUBLISHED
        if "start_pipeline" in body and body["start_pipeline"]
        else RunningState.NOT_STARTED
    )
    pipeline: Dict[str, List[str]] = FULL_PROJECT_PIPELINE_ADJACENCY
    node_states = FULL_PROJECT_NODE_STATES
    if body.get("subgraph"):
        # create some fake adjacency list
        pipeline = {}
        node_states = {}
        for node_id in body.get("subgraph"):
            pipeline[node_id] = [
                "62237c33-8d6c-4709-aa92-c3cf693dd6d2",
                "0bdf824f-57cb-4e38-949e-fd12c184f000",
            ]
            node_states[node_id] = {"state": {"modified": True, "dependencies": []}}
        node_states["62237c33-8d6c-4709-aa92-c3cf693dd6d2"] = {
            "modified": True,
            "dependencies": ["2f493631-30b4-4ad8-90f2-a74e4b46fe73"],
        }
        node_states["0bdf824f-57cb-4e38-949e-fd12c184f000"] = {
            "modified": True,
            "dependencies": [
                "2f493631-30b4-4ad8-90f2-a74e4b46fe73",
                "62237c33-8d6c-4709-aa92-c3cf693dd6d2",
            ],
        }

    return CallbackResult(
        status=201,
        # NOTE: aioresponses uses json.dump which does NOT encode serialization of UUIDs
        payload={
            "id": str(kwargs["json"]["project_id"]),
            "state": state,
            "pipeline_details": {
                "adjacency_list": pipeline,
                "node_states": node_states,
            },
        },
    )


def get_computation_cb(url, **kwargs) -> CallbackResult:
    state = RunningState.NOT_STARTED
    pipeline: Dict[str, List[str]] = FULL_PROJECT_PIPELINE_ADJACENCY
    node_states = FULL_PROJECT_NODE_STATES

    return CallbackResult(
        status=202,
        payload={
            "id": Path(url.path).name,
            "state": state,
            "pipeline_details": {
                "adjacency_list": pipeline,
                "node_states": node_states,
            },
        },
    )


def create_cluster_cb(url, **kwargs) -> CallbackResult:
    assert "json" in kwargs, f"missing body in call to {url}"
    body = kwargs["json"]
    assert url.query.get("user_id")
    random_cluster = Cluster.parse_obj(
        random.choice(Cluster.Config.schema_extra["examples"])
    )
    return CallbackResult(status=201, payload=random_cluster.dict(by_alias=True))


def list_clusters_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    return CallbackResult(
        status=200,
        body=json.dumps(
            [
                Cluster.parse_obj(
                    random.choice(Cluster.Config.schema_extra["examples"])
                ).dict(by_alias=True)
                for _ in range(3)
            ]
        ),
    )


def get_cluster_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    cluster_id = url.path.split("/")[-1]
    return CallbackResult(
        status=200,
        payload=Cluster.parse_obj(
            {
                **random.choice(Cluster.Config.schema_extra["examples"]),
                **{"id": cluster_id},
            }
        ).dict(by_alias=True),
    )


def get_cluster_details_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    cluster_id = url.path.split("/")[-1]
    return CallbackResult(
        status=200,
        payload={"scheduler": {}, "cluster": {}, "dashboard_link": "some_faked_link"},
    )


def patch_cluster_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    cluster_id = url.path.split("/")[-1]
    return CallbackResult(
        status=200,
        payload=Cluster.parse_obj(
            {
                **random.choice(Cluster.Config.schema_extra["examples"]),
                **{"id": cluster_id},
            }
        ).dict(by_alias=True),
    )


@pytest.fixture
async def director_v2_service_mock(
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    """mocks responses of director-v2"""

    # computations
    create_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations$"
    )

    get_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*$"
    )
    stop_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*:stop$"
    )
    delete_computation_pattern = get_computation_pattern

    aioresponses_mocker.post(
        create_computation_pattern,
        callback=create_computation_cb,
        status=web.HTTPCreated.status_code,
        repeat=True,
    )
    aioresponses_mocker.post(
        stop_computation_pattern,
        status=web.HTTPAccepted.status_code,
        repeat=True,
    )
    aioresponses_mocker.get(
        get_computation_pattern,
        status=web.HTTPAccepted.status_code,
        callback=get_computation_cb,
        repeat=True,
    )
    aioresponses_mocker.delete(delete_computation_pattern, status=204, repeat=True)

    # clusters
    cluster_route_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)?\?(\w+(?:=\w+)?\&?){1,}$"
    )
    aioresponses_mocker.post(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=create_cluster_cb,
        status=web.HTTPCreated.status_code,
        repeat=True,
    )

    aioresponses_mocker.get(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=list_clusters_cb,
        status=web.HTTPCreated.status_code,
        repeat=True,
    )

    aioresponses_mocker.get(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=get_cluster_cb,
        status=web.HTTPCreated.status_code,
        repeat=True,
    )

    aioresponses_mocker.get(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters/[0-9]+/details\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=get_cluster_details_cb,
        status=web.HTTPCreated.status_code,
        repeat=True,
    )

    aioresponses_mocker.patch(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=patch_cluster_cb,
        status=web.HTTPCreated.status_code,
        repeat=True,
    )
    aioresponses_mocker.delete(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        status=web.HTTPNoContent.status_code,
        repeat=True,
    )

    return aioresponses_mocker


@pytest.fixture
async def storage_v0_service_mock(
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    """mocks responses of storage API"""

    def get_download_link_cb(url: URL, **kwargs) -> CallbackResult:
        file_id = url.path.rsplit("/files/")[1]

        return CallbackResult(
            status=web.HTTPOk.status_code,
            payload={"data": {"link": f"file://{file_id}"}},
        )

    get_file_metadata_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+/metadata.+$"
    )

    get_upload_link_pattern = get_download_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+$"
    )

    get_locations_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations.*$"
    )

    aioresponses_mocker.get(
        get_file_metadata_pattern,
        status=web.HTTPOk.status_code,
        payload={"data": FileMetaData.Config.schema_extra["examples"][0]},
    )
    aioresponses_mocker.get(
        get_download_link_pattern, callback=get_download_link_cb, repeat=True
    )
    aioresponses_mocker.put(
        get_upload_link_pattern, callback=get_download_link_cb, repeat=True
    )
    aioresponses_mocker.get(
        get_locations_link_pattern,
        status=web.HTTPOk.status_code,
        payload={"data": [{"name": "simcore.s3", "id": "0"}]},
    )

    return aioresponses_mocker
