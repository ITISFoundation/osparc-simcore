# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import random
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import pytest
from aioresponses import aioresponses as AioResponsesMock
from aioresponses.core import CallbackResult
from faker import Faker
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadLinks,
    FileUploadSchema,
    LinkType,
    PresignedLink,
)
from models_library.clusters import Cluster
from models_library.generics import Envelope
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.aiohttp import status
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aioresponses_mocker",
]

# The adjacency list is defined as a dictionary with the key to the node and its list of successors
FULL_PROJECT_PIPELINE_ADJACENCY: dict[str, list[str]] = {
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

FULL_PROJECT_NODE_STATES: dict[str, dict[str, Any]] = {
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
    pipeline: dict[str, list[str]] = FULL_PROJECT_PIPELINE_ADJACENCY
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
    returned_computation = ComputationTask.model_validate(
        ComputationTask.model_config["json_schema_extra"]["examples"][0]
    ).model_copy(
        update={
            "id": f"{kwargs['json']['project_id']}",
            "state": state,
            "pipeline_details": {
                "adjacency_list": pipeline,
                "node_states": node_states,
                "progress": 0,
            },
        }
    )
    return CallbackResult(
        status=201,
        # NOTE: aioresponses uses json.dump which does NOT encode serialization of UUIDs
        payload=jsonable_encoder(returned_computation),
    )


def get_computation_cb(url, **kwargs) -> CallbackResult:
    state = RunningState.NOT_STARTED
    pipeline: dict[str, list[str]] = FULL_PROJECT_PIPELINE_ADJACENCY
    node_states = FULL_PROJECT_NODE_STATES
    returned_computation = ComputationTask.model_validate(
        ComputationTask.model_config["json_schema_extra"]["examples"][0]
    ).model_copy(
        update={
            "id": Path(url.path).name,
            "state": state,
            "pipeline_details": {
                "adjacency_list": pipeline,
                "node_states": node_states,
                "progress": 0,
            },
        }
    )

    return CallbackResult(
        status=200,
        payload=jsonable_encoder(returned_computation),
    )


def create_cluster_cb(url, **kwargs) -> CallbackResult:
    assert "json" in kwargs, f"missing body in call to {url}"
    assert url.query.get("user_id")
    random_cluster = Cluster.model_validate(
        random.choice(Cluster.model_config["json_schema_extra"]["examples"])
    )
    return CallbackResult(
        status=201, payload=json.loads(random_cluster.model_dump_json(by_alias=True))
    )


def list_clusters_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    return CallbackResult(
        status=200,
        body=json.dumps(
            [
                json.loads(
                    Cluster.model_validate(
                        random.choice(
                            Cluster.model_config["json_schema_extra"]["examples"]
                        )
                    ).model_dump_json(by_alias=True)
                )
                for _ in range(3)
            ]
        ),
    )


def get_cluster_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    cluster_id = url.path.split("/")[-1]
    return CallbackResult(
        status=200,
        payload=json.loads(
            Cluster.model_validate(
                {
                    **random.choice(
                        Cluster.model_config["json_schema_extra"]["examples"]
                    ),
                    **{"id": cluster_id},
                }
            ).model_dump_json(by_alias=True)
        ),
    )


def get_cluster_details_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    cluster_id = url.path.split("/")[-1]
    assert cluster_id
    return CallbackResult(
        status=200,
        payload={
            "scheduler": {"status": "RUNNING"},
            "dashboard_link": "https://dashboard.link.com",
        },
    )


def patch_cluster_cb(url, **kwargs) -> CallbackResult:
    assert url.query.get("user_id")
    cluster_id = url.path.split("/")[-1]
    return CallbackResult(
        status=200,
        payload=json.loads(
            Cluster.model_validate(
                {
                    **random.choice(
                        Cluster.model_config["json_schema_extra"]["examples"]
                    ),
                    **{"id": cluster_id},
                }
            ).model_dump_json(by_alias=True)
        ),
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
    projects_networks_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/dynamic_services/projects/.*/-/networks$"
    )

    get_services_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/dynamic_services.*$"
    )

    aioresponses_mocker.get(
        get_services_pattern, status=status.HTTP_200_OK, repeat=True
    )

    aioresponses_mocker.post(
        create_computation_pattern,
        callback=create_computation_cb,
        status=status.HTTP_201_CREATED,
        repeat=True,
    )
    aioresponses_mocker.post(
        stop_computation_pattern,
        status=status.HTTP_202_ACCEPTED,
        repeat=True,
    )
    aioresponses_mocker.get(
        get_computation_pattern,
        status=status.HTTP_202_ACCEPTED,
        callback=get_computation_cb,
        repeat=True,
    )
    aioresponses_mocker.delete(delete_computation_pattern, status=204, repeat=True)
    aioresponses_mocker.patch(projects_networks_pattern, status=204, repeat=True)

    # clusters
    aioresponses_mocker.post(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=create_cluster_cb,
        status=status.HTTP_201_CREATED,
        repeat=True,
    )

    aioresponses_mocker.get(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=list_clusters_cb,
        status=status.HTTP_201_CREATED,
        repeat=True,
    )

    aioresponses_mocker.get(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=get_cluster_cb,
        status=status.HTTP_201_CREATED,
        repeat=True,
    )

    aioresponses_mocker.get(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters/[0-9]+/details\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=get_cluster_details_cb,
        status=status.HTTP_201_CREATED,
        repeat=True,
    )

    aioresponses_mocker.patch(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        callback=patch_cluster_cb,
        status=status.HTTP_201_CREATED,
        repeat=True,
    )
    aioresponses_mocker.delete(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+)\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        status=status.HTTP_204_NO_CONTENT,
        repeat=True,
    )

    aioresponses_mocker.post(
        re.compile(r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters:ping$"),
        status=status.HTTP_204_NO_CONTENT,
        repeat=True,
    )

    aioresponses_mocker.post(
        re.compile(
            r"^http://[a-z\-_]*director-v2:[0-9]+/v2/clusters(/[0-9]+):ping\?(\w+(?:=\w+)?\&?){1,}$"
        ),
        status=status.HTTP_204_NO_CONTENT,
        repeat=True,
    )

    return aioresponses_mocker


def get_download_link_cb(url: URL, **kwargs) -> CallbackResult:
    file_id = url.path.rsplit("/files/")[1]
    assert "params" in kwargs
    assert "link_type" in kwargs["params"]
    link_type = kwargs["params"]["link_type"]
    scheme = {LinkType.PRESIGNED: "http", LinkType.S3: "s3"}
    return CallbackResult(
        status=status.HTTP_200_OK,
        payload={"data": {"link": f"{scheme[link_type]}://{file_id}"}},
    )


def get_upload_link_cb(url: URL, **kwargs) -> CallbackResult:
    file_id = url.path.rsplit("/files/")[1]
    assert "params" in kwargs
    assert "link_type" in kwargs["params"]
    link_type = kwargs["params"]["link_type"]
    scheme = {LinkType.PRESIGNED: "http", LinkType.S3: "s3"}

    if file_size := kwargs["params"].get("file_size") is not None:
        assert file_size
        upload_schema = FileUploadSchema(
            chunk_size=TypeAdapter(ByteSize).validate_python("5GiB"),
            urls=[
                TypeAdapter(AnyUrl).validate_python(f"{scheme[link_type]}://{file_id}")
            ],
            links=FileUploadLinks(
                abort_upload=TypeAdapter(AnyUrl).validate_python(f"{url}:abort"),
                complete_upload=TypeAdapter(AnyUrl).validate_python(f"{url}:complete"),
            ),
        )
        return CallbackResult(
            status=status.HTTP_200_OK,
            payload={"data": jsonable_encoder(upload_schema)},
        )
    # version 1 returns a presigned link
    presigned_link = PresignedLink(
        link=TypeAdapter(AnyUrl).validate_python(f"{scheme[link_type]}://{file_id}")
    )
    return CallbackResult(
        status=status.HTTP_200_OK,
        payload={"data": jsonable_encoder(presigned_link)},
    )


def list_file_meta_data_cb(url: URL, **kwargs) -> CallbackResult:
    assert "params" in kwargs
    assert "user_id" in kwargs["params"]
    assert "uuid_filter" in kwargs["params"]
    return CallbackResult(
        status=status.HTTP_200_OK,
        payload=jsonable_encoder(Envelope[list[FileMetaDataGet]](data=[])),
    )


@pytest.fixture
async def storage_v0_service_mock(
    aioresponses_mocker: AioResponsesMock, faker: Faker
) -> AioResponsesMock:
    """mocks responses of storage API"""

    get_file_metadata_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+/metadata.+$"
    )

    get_upload_link_pattern = (
        get_download_link_pattern
    ) = delete_file_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files.+$"
    )

    get_locations_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations.+$"
    )

    list_file_meta_data_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/metadata.+$"
    )

    storage_complete_link = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+complete"
    )

    storage_complete_link_futures = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+complete/futures/.+"
    )

    storage_abort_link = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+abort"
    )

    aioresponses_mocker.get(
        get_file_metadata_pattern,
        status=status.HTTP_200_OK,
        payload={
            "data": FileMetaDataGet.model_config["json_schema_extra"]["examples"][0]
        },
        repeat=True,
    )
    aioresponses_mocker.get(
        list_file_meta_data_pattern,
        callback=list_file_meta_data_cb,
        repeat=True,
    )
    aioresponses_mocker.get(
        get_download_link_pattern, callback=get_download_link_cb, repeat=True
    )
    aioresponses_mocker.put(
        get_upload_link_pattern, callback=get_upload_link_cb, repeat=True
    )
    aioresponses_mocker.delete(delete_file_pattern, status=status.HTTP_204_NO_CONTENT)

    aioresponses_mocker.get(
        get_locations_link_pattern,
        status=status.HTTP_200_OK,
        payload={"data": [{"name": "simcore.s3", "id": 0}]},
        repeat=True,
    )

    def generate_future_link(url, **kwargs):
        parsed_url = urlparse(str(url))
        stripped_url = urlunparse(
            (parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "", "")
        )

        payload: FileUploadCompleteResponse = TypeAdapter(
            FileUploadCompleteResponse
        ).validate_python(
            {
                "links": {
                    "state": stripped_url + ":complete/futures/" + str(faker.uuid4())
                },
            },
        )
        return CallbackResult(
            status=status.HTTP_200_OK,
            payload=jsonable_encoder(
                Envelope[FileUploadCompleteResponse](data=payload)
            ),
        )

    aioresponses_mocker.post(storage_complete_link, callback=generate_future_link)

    aioresponses_mocker.post(
        storage_complete_link_futures,
        status=status.HTTP_200_OK,
        payload=jsonable_encoder(
            Envelope[FileUploadCompleteFutureResponse](
                data=FileUploadCompleteFutureResponse(
                    state=FileUploadCompleteState.OK,
                    e_tag="07d1c1a4-b073-4be7-b022-f405d90e99aa",
                )
            )
        ),
    )

    aioresponses_mocker.post(
        storage_abort_link,
        status=status.HTTP_200_OK,
    )

    return aioresponses_mocker
