# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from aioresponses import aioresponses as AioResponsesMock
from aioresponses.core import CallbackResult
from faker import Faker
from models_library.api_schemas_directorv2.comp_tasks import ComputationGet
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
from models_library.generics import Envelope
from models_library.projects_nodes import NodeID, NodeState
from models_library.projects_pipeline import ComputationTask, PipelineDetails, TaskID
from models_library.projects_state import RunningState
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.aiohttp import status
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aioresponses_mocker",
]

# The adjacency list is defined as a dictionary with the key to the node and its list of successors
FULL_PROJECT_PIPELINE_ADJACENCY: dict[NodeID, list[NodeID]] = {
    NodeID("62bca361-8594-48c8-875e-b8577e868aec"): [
        NodeID("e0d7a1a5-0700-42c7-b033-97f72ac4a5cd"),
        NodeID("5284bb5b-b068-4d0e-9075-3d5d8eec5060"),
        NodeID("750454a8-b450-43ce-a012-40b669f7d28c"),
    ],
    NodeID("e0d7a1a5-0700-42c7-b033-97f72ac4a5cd"): [
        NodeID("e83a359a-1efe-41d3-83aa-a285afbfaf12")
    ],
    NodeID("5284bb5b-b068-4d0e-9075-3d5d8eec5060"): [
        NodeID("e83a359a-1efe-41d3-83aa-a285afbfaf12")
    ],
    NodeID("750454a8-b450-43ce-a012-40b669f7d28c"): [
        NodeID("e83a359a-1efe-41d3-83aa-a285afbfaf12")
    ],
    NodeID("e83a359a-1efe-41d3-83aa-a285afbfaf12"): [],
}

FULL_PROJECT_NODE_STATES: dict[NodeID, NodeState] = {
    NodeID("62bca361-8594-48c8-875e-b8577e868aec"): NodeState.model_construct(
        **{"modified": True, "dependencies": set()}
    ),
    NodeID("e0d7a1a5-0700-42c7-b033-97f72ac4a5cd"): NodeState.model_construct(
        **{
            "modified": True,
            "dependencies": {NodeID("62bca361-8594-48c8-875e-b8577e868aec")},
        }
    ),
    NodeID("5284bb5b-b068-4d0e-9075-3d5d8eec5060"): NodeState.model_construct(
        **{
            "modified": True,
            "dependencies": {NodeID("62bca361-8594-48c8-875e-b8577e868aec")},
        }
    ),
    NodeID("750454a8-b450-43ce-a012-40b669f7d28c"): NodeState.model_construct(
        **{
            "modified": True,
            "dependencies": {NodeID("62bca361-8594-48c8-875e-b8577e868aec")},
        }
    ),
    NodeID("e83a359a-1efe-41d3-83aa-a285afbfaf12"): NodeState.model_construct(
        **{
            "modified": True,
            "dependencies": {
                NodeID("e0d7a1a5-0700-42c7-b033-97f72ac4a5cd"),
                NodeID("5284bb5b-b068-4d0e-9075-3d5d8eec5060"),
                NodeID("750454a8-b450-43ce-a012-40b669f7d28c"),
            },
        }
    ),
}


def create_computation_cb(url, **kwargs) -> CallbackResult:
    assert "json" in kwargs, f"missing body in call to {url}"
    body = kwargs["json"]
    for param in ["user_id", "project_id"]:
        assert param in body, f"{param} is missing from body: {body}"
    state = (
        RunningState.PUBLISHED
        if body.get("start_pipeline")
        else RunningState.NOT_STARTED
    )
    pipeline: dict[NodeID, list[str]] = FULL_PROJECT_PIPELINE_ADJACENCY
    node_states = FULL_PROJECT_NODE_STATES
    if body.get("subgraph"):
        # create some fake adjacency list
        pipeline = {}
        node_states = {}
        for node_id in body.get("subgraph"):
            pipeline[NodeID(node_id)] = [
                NodeID("62237c33-8d6c-4709-aa92-c3cf693dd6d2"),
                NodeID("0bdf824f-57cb-4e38-949e-fd12c184f000"),
            ]
            node_states[NodeID(node_id)] = NodeState.model_construct(
                **{"state": {"modified": True, "dependencies": []}}
            )
        node_states[
            NodeID("62237c33-8d6c-4709-aa92-c3cf693dd6d2")
        ] = NodeState.model_construct(
            **{
                "modified": True,
                "dependencies": {NodeID("2f493631-30b4-4ad8-90f2-a74e4b46fe73")},
            }
        )
        node_states[
            NodeID("0bdf824f-57cb-4e38-949e-fd12c184f000")
        ] = NodeState.model_construct(
            **{
                "modified": True,
                "dependencies": {
                    NodeID("2f493631-30b4-4ad8-90f2-a74e4b46fe73"),
                    NodeID("62237c33-8d6c-4709-aa92-c3cf693dd6d2"),
                },
            }
        )
    returned_computation = ComputationTask.model_validate(
        ComputationTask.model_config["json_schema_extra"]["examples"][0]
    ).model_copy(
        update={
            "id": TaskID(f"{kwargs['json']['project_id']}"),
            "state": state,
            "pipeline_details": PipelineDetails.model_construct(
                **{
                    "adjacency_list": pipeline,
                    "node_states": node_states,
                    "progress": 0,
                }
            ),
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
    assert "json_schema_extra" in ComputationGet.model_config
    assert isinstance(ComputationGet.model_config["json_schema_extra"], dict)
    assert isinstance(
        ComputationGet.model_config["json_schema_extra"]["examples"], list
    )
    returned_computation = ComputationGet.model_validate(
        ComputationGet.model_config["json_schema_extra"]["examples"][0]
    ).model_copy(
        update={
            "id": TaskID(Path(url.path).name),
            "state": state,
            "pipeline_details": PipelineDetails.model_construct(
                **{
                    "adjacency_list": pipeline,
                    "node_states": node_states,
                    "progress": 0,
                }
            ),
        }
    )

    return CallbackResult(
        status=200,
        payload=jsonable_encoder(returned_computation),
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
