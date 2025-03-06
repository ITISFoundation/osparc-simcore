# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


import logging
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeAlias

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobId
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_webserver.storage import StorageAsyncJobGet
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.storage_utils import FileIDDict, ProjectWithFilesParams
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import (
    get_result,
    get_status,
)
from servicelib.rabbitmq.rpc_interfaces.storage.paths import compute_path_size
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]

_IsFile: TypeAlias = bool


@pytest.fixture
async def storage_rabbitmq_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("pytest_storage_rpc_client")
    assert rpc_client
    return rpc_client


def _filter_and_group_paths_one_level_deeper(
    paths: list[Path], prefix: Path
) -> list[tuple[Path, _IsFile]]:
    relative_paths = (path for path in paths if path.is_relative_to(prefix))
    return sorted(
        {
            (
                (path, len(path.relative_to(prefix).parts) == 1)
                if len(path.relative_to(prefix).parts) == 1
                else (prefix / path.relative_to(prefix).parts[0], False)
            )
            for path in relative_paths
        },
        key=lambda x: x[0],
    )


_logger = logging.getLogger(__name__)


async def _assert_compute_path_size(
    rpc_client: RabbitMQRPCClient,
    location_id: LocationID,
    user_id: UserID,
    *,
    path: Path,
    expected_total_size: int,
) -> ByteSize:
    received, job_id_data = await compute_path_size(
        rpc_client, user_id=user_id, product_name="", location_id=location_id, path=path
    )

    assert isinstance(received, StorageAsyncJobGet)

    @retry(
        wait=wait_fixed(1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )
    async def _wait_for_job_completion(job_id: AsyncJobId) -> None:
        job_status = await get_status(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            job_id=job_id,
            job_id_data=job_id_data,
        )
        assert job_status.done

    await _wait_for_job_completion(received.job_id)
    job_result = await get_result(
        rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=received.job_id,
        job_id_data=job_id_data,
    )
    assert job_result.result is not None
    assert job_result.error is None
    response = job_result.result
    assert isinstance(response, ByteSize)
    assert response == expected_total_size
    return response


@pytest.mark.xfail(reason="in development")
@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=5,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
            workspace_files_count=10,
        )
    ],
    ids=str,
)
async def test_path_compute_size(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    location_id: LocationID,
    user_id: UserID,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    project_params: ProjectWithFilesParams,
):
    assert (
        len(project_params.allowed_file_sizes) == 1
    ), "test preconditions are not filled! allowed file sizes should have only 1 option for this test"
    project, list_of_files = with_random_project_with_files

    total_num_files = sum(
        len(files_in_node) for files_in_node in list_of_files.values()
    )

    # get size of a full project
    expected_total_size = project_params.allowed_file_sizes[0] * total_num_files
    path = Path(project["uuid"])
    await _assert_compute_path_size(
        storage_rabbitmq_rpc_client,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
    )

    # get size of one of the nodes
    selected_node_id = NodeID(random.choice(list(project["workbench"])))  # noqa: S311
    path = Path(project["uuid"]) / f"{selected_node_id}"
    selected_node_s3_keys = [
        Path(s3_object_id) for s3_object_id in list_of_files[selected_node_id]
    ]
    expected_total_size = project_params.allowed_file_sizes[0] * len(
        selected_node_s3_keys
    )
    await _assert_compute_path_size(
        storage_rabbitmq_rpc_client,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
    )

    # get size of the outputs of one of the nodes
    path = Path(project["uuid"]) / f"{selected_node_id}" / "outputs"
    selected_node_s3_keys = [
        Path(s3_object_id)
        for s3_object_id in list_of_files[selected_node_id]
        if s3_object_id.startswith(f"{path}")
    ]
    expected_total_size = project_params.allowed_file_sizes[0] * len(
        selected_node_s3_keys
    )
    await _assert_compute_path_size(
        storage_rabbitmq_rpc_client,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
    )

    # get size of workspace in one of the nodes (this is semi-cached in the DB)
    path = Path(project["uuid"]) / f"{selected_node_id}" / "workspace"
    selected_node_s3_keys = [
        Path(s3_object_id)
        for s3_object_id in list_of_files[selected_node_id]
        if s3_object_id.startswith(f"{path}")
    ]
    expected_total_size = project_params.allowed_file_sizes[0] * len(
        selected_node_s3_keys
    )
    workspace_total_size = await _assert_compute_path_size(
        storage_rabbitmq_rpc_client,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
    )

    # get size of folders inside the workspace
    folders_inside_workspace = [
        p[0]
        for p in _filter_and_group_paths_one_level_deeper(selected_node_s3_keys, path)
        if p[1] is False
    ]
    accumulated_subfolder_size = 0
    for workspace_subfolder in folders_inside_workspace:
        selected_node_s3_keys = [
            Path(s3_object_id)
            for s3_object_id in list_of_files[selected_node_id]
            if s3_object_id.startswith(f"{workspace_subfolder}")
        ]
        expected_total_size = project_params.allowed_file_sizes[0] * len(
            selected_node_s3_keys
        )
        accumulated_subfolder_size += await _assert_compute_path_size(
            storage_rabbitmq_rpc_client,
            location_id,
            user_id,
            path=workspace_subfolder,
            expected_total_size=expected_total_size,
        )

    assert workspace_total_size == accumulated_subfolder_size


@pytest.mark.xfail(reason="in development")
async def test_path_compute_size_inexistent_path(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    location_id: LocationID,
    user_id: UserID,
    faker: Faker,
    fake_datcore_tokens: tuple[str, str],
):
    await _assert_compute_path_size(
        storage_rabbitmq_rpc_client,
        location_id,
        user_id,
        path=Path(faker.file_path(absolute=False)),
        expected_total_size=0,
    )
