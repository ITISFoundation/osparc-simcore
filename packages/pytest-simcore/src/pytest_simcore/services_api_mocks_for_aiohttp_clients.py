import re
from pathlib import Path
from typing import Dict, List

import pytest
from aioresponses import aioresponses
from aioresponses.core import CallbackResult
from models_library.projects_state import RunningState
from yarl import URL

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

FULL_PROJECT_NODE_STATES: Dict[str, Dict[str, str]] = {
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


def creation_cb(url, **kwargs) -> CallbackResult:

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
        payload={
            "id": kwargs["json"]["project_id"],
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


@pytest.fixture
async def director_v2_service_mock() -> aioresponses:

    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]
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
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.post(
            create_computation_pattern,
            callback=creation_cb,
            repeat=True,
        )
        mock.post(
            stop_computation_pattern,
            status=204,
            repeat=True,
        )
        mock.get(
            get_computation_pattern,
            status=202,
            callback=get_computation_cb,
            repeat=True,
        )
        mock.delete(delete_computation_pattern, status=204, repeat=True)

        yield mock


@pytest.fixture
async def storage_v0_service_mock() -> aioresponses:

    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]

    def get_download_link_cb(url: URL, **kwargs) -> CallbackResult:
        file_id = url.path.rsplit("/files/")[1]

        return CallbackResult(
            status=200, payload={"data": {"link": f"file://{file_id}"}}
        )

    get_download_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+$"
    )

    get_locations_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations.*$"
    )

    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.get(get_download_link_pattern, callback=get_download_link_cb, repeat=True)
        mock.get(
            get_locations_link_pattern,
            status=200,
            payload={"data": [{"name": "simcore.s3", "id": "0"}]},
        )
        yield mock
