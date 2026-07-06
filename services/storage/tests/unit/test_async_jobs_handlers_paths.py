# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


import datetime
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

import pytest
from aws_library.s3 import SimcoreS3API
from celery.worker.worker import WorkController
from celery_library.async_jobs import (
    submit_job,
    wait_and_get_job_result,
)
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobResult,
)
from models_library.basic_types import SHA256Str
from models_library.celery import OwnerMetadata, TaskExecutionMetadata, Wildcard
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.storage_utils import FileIDDict, ProjectWithFilesParams, get_updated_project
from servicelib.celery.task_manager import TaskManager
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage.models import FileMetaData, FileMetaDataAtDB, S3BucketName
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer"]

type _IsFile = bool


class TestOwnerMetadata(OwnerMetadata):
    user_id: int | Wildcard
    product_name: str | Wildcard


def _filter_and_group_paths_one_level_deeper(paths: list[Path], prefix: Path) -> list[tuple[Path, _IsFile]]:
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


async def _assert_compute_path_size(
    task_manager: TaskManager,
    location_id: LocationID,
    user_id: UserID,
    product_name: ProductName,
    *,
    path: Path,
    expected_total_size: int,
) -> ByteSize:
    async_job = await submit_job(
        task_manager,
        execution_metadata=TaskExecutionMetadata(name="compute_path_size"),
        owner_metadata=TestOwnerMetadata(user_id=user_id, product_name=product_name, owner="pytest_client_name"),
        location_id=location_id,
        path=path,
        user_id=user_id,
        product_name=product_name,
    )
    async for job_composed_result in wait_and_get_job_result(
        task_manager,
        owner_metadata=TestOwnerMetadata(user_id=user_id, product_name=product_name, owner="pytest_client_name"),
        job_id=async_job.job_id,
        stop_after=datetime.timedelta(seconds=120),
    ):
        if job_composed_result.done:
            response = await job_composed_result.result()
            assert isinstance(response, AsyncJobResult)
            received_size = TypeAdapter(ByteSize).validate_python(response.result)
            assert received_size == expected_total_size
            return received_size

    pytest.fail("Job did not finish")
    return ByteSize(0)  # for mypy


async def _assert_delete_paths(
    task_manager: TaskManager,
    location_id: LocationID,
    user_id: UserID,
    product_name: ProductName,
    *,
    paths: set[Path],
) -> None:
    async_job = await submit_job(
        task_manager,
        execution_metadata=TaskExecutionMetadata(name="delete_paths"),
        owner_metadata=TestOwnerMetadata(user_id=user_id, product_name=product_name, owner="pytest_client_name"),
        location_id=location_id,
        user_id=user_id,
        paths=paths,
    )
    async for job_composed_result in wait_and_get_job_result(
        task_manager,
        owner_metadata=TestOwnerMetadata(user_id=user_id, product_name=product_name, owner="pytest_client_name"),
        job_id=async_job.job_id,
        stop_after=datetime.timedelta(seconds=120),
    ):
        if job_composed_result.done:
            response = await job_composed_result.result()
            assert isinstance(response, AsyncJobResult)
            assert response.result is None
            return

    pytest.fail("Job did not finish")


@pytest.fixture
async def with_seeded_project_with_files(
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_bucket: S3BucketName,
    storage_s3_client: SimcoreS3API,
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_project_node: Callable[..., Awaitable[tuple[NodeID, Any]]],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str, Path | None], SimcoreS3FileID],
    faker: Faker,
    project_params: ProjectWithFilesParams,
    user_id: UserID,
    with_storage_celery_worker: WorkController,
) -> tuple[
    dict[str, Any],
    dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
]:
    assert project_params.allowed_file_sizes

    def _select_checksum() -> SHA256Str:
        if project_params.allowed_file_checksums:
            return random.choice(project_params.allowed_file_checksums)  # noqa: S311
        return TypeAdapter(SHA256Str).validate_python(faker.sha256(raw_output=False))

    project = await create_project(name="seeded-random-project")
    project_id = ProjectID(project["uuid"])
    location_id = SimcoreS3DataManager.get_location_id()
    location_name = SimcoreS3DataManager.get_location_name()

    files_by_node: dict[NodeID, dict[SimcoreS3FileID, FileIDDict]] = {}
    db_entries: list[dict[str, Any]] = []
    local_files_by_size: dict[ByteSize, Path] = {}

    for _ in range(project_params.num_nodes):
        node_id = cast(NodeID, faker.uuid4(cast_to=None))
        files_by_node[node_id] = {}

        output_file_name = faker.file_name()
        output_file_id = create_simcore_file_id(project_id, node_id, output_file_name, Path("outputs/output_3"))
        created_node_id, _ = await create_project_node(
            project_id,
            node_id,
            outputs={
                "output_1": faker.pyint(),
                "output_2": faker.pystr(),
                "output_3": f"{output_file_id}",
            },
        )
        assert created_node_id == node_id

        file_specs: list[tuple[SimcoreS3FileID, ByteSize, SHA256Str]] = []
        # One tracked output file per node
        file_specs.append(
            (
                output_file_id,
                random.choice(project_params.allowed_file_sizes),  # noqa: S311
                _select_checksum(),
            )
        )

        # Root-level files keep deletion-path coverage without full upload completion setup.
        for _ in range(2):
            root_name = faker.file_name()
            root_file_id = create_simcore_file_id(project_id, node_id, root_name, None)
            file_specs.append(
                (
                    root_file_id,
                    random.choice(project_params.allowed_file_sizes),  # noqa: S311
                    _select_checksum(),
                )
            )

        # Workspace files distributed across subfolders preserve path grouping checks.
        workspace_subdirs = [Path("workspace") / f"sub-dir_etc ory-{index}" for index in range(3)]
        for index in range(project_params.workspace_files_count):
            workspace_name = faker.file_name()
            file_specs.append(
                (
                    create_simcore_file_id(
                        project_id,
                        node_id,
                        workspace_name,
                        workspace_subdirs[index % len(workspace_subdirs)],
                    ),
                    random.choice(project_params.allowed_file_sizes),  # noqa: S311
                    _select_checksum(),
                )
            )

        for file_id, file_size, file_checksum in file_specs:
            if file_size not in local_files_by_size:
                local_files_by_size[file_size] = create_file_of_size(file_size, None)

            local_file = local_files_by_size[file_size]
            await storage_s3_client.upload_file(
                bucket=storage_s3_bucket,
                file=local_file,
                object_key=file_id,
                bytes_transferred_cb=None,
            )

            files_by_node[node_id][file_id] = FileIDDict(path=local_file, sha256_checksum=file_checksum)
            db_fmd = FileMetaData.from_simcore_node(
                user_id=user_id,
                file_id=file_id,
                bucket=storage_s3_bucket,
                location_id=location_id,
                location_name=location_name,
                sha256_checksum=file_checksum,
                file_size=file_size,
                entity_tag=f"seeded-{faker.md5(raw_output=False)}",
                upload_id=None,
                upload_expires_at=None,
                is_directory=False,
            )
            db_entries.append(jsonable_encoder(FileMetaDataAtDB.model_validate(db_fmd)))

    async with sqlalchemy_async_engine.begin() as connection:
        await connection.execute(file_meta_data.insert(), db_entries)

    project = await get_updated_project(sqlalchemy_async_engine, project["uuid"])
    return project, files_by_node


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
    task_manager: TaskManager,
    user_id: UserID,
    location_id: LocationID,
    with_seeded_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    project_params: ProjectWithFilesParams,
    product_name: ProductName,
):
    assert len(project_params.allowed_file_sizes) == 1, (
        "test preconditions are not filled! allowed file sizes should have only 1 option for this test"
    )
    project, list_of_files = with_seeded_project_with_files

    total_num_files = sum(len(files_in_node) for files_in_node in list_of_files.values())

    # get size of a full project
    expected_total_size = project_params.allowed_file_sizes[0] * total_num_files
    path = Path(project["uuid"])
    await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
        product_name=product_name,
    )

    # get size of one of the nodes
    selected_node_id = NodeID(random.choice(list(project["workbench"])))  # noqa: S311
    path = Path(project["uuid"]) / f"{selected_node_id}"
    selected_node_s3_keys = [Path(s3_object_id) for s3_object_id in list_of_files[selected_node_id]]
    expected_total_size = project_params.allowed_file_sizes[0] * len(selected_node_s3_keys)
    await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
        product_name=product_name,
    )

    # get size of the outputs of one of the nodes
    path = Path(project["uuid"]) / f"{selected_node_id}" / "outputs"
    selected_node_s3_keys = [
        Path(s3_object_id) for s3_object_id in list_of_files[selected_node_id] if s3_object_id.startswith(f"{path}")
    ]
    expected_total_size = project_params.allowed_file_sizes[0] * len(selected_node_s3_keys)
    await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
        product_name=product_name,
    )

    # get size of workspace in one of the nodes (this is semi-cached in the DB)
    path = Path(project["uuid"]) / f"{selected_node_id}" / "workspace"
    selected_node_s3_keys = [
        Path(s3_object_id) for s3_object_id in list_of_files[selected_node_id] if s3_object_id.startswith(f"{path}")
    ]
    expected_total_size = project_params.allowed_file_sizes[0] * len(selected_node_s3_keys)
    workspace_total_size = await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
        product_name=product_name,
    )

    # get size of folders inside the workspace
    folders_inside_workspace = [
        p[0] for p in _filter_and_group_paths_one_level_deeper(selected_node_s3_keys, path) if p[1] is False
    ]
    accumulated_subfolder_size = 0
    for workspace_subfolder in folders_inside_workspace:
        selected_node_s3_keys = [
            Path(s3_object_id)
            for s3_object_id in list_of_files[selected_node_id]
            if s3_object_id.startswith(f"{workspace_subfolder}")
        ]
        expected_total_size = project_params.allowed_file_sizes[0] * len(selected_node_s3_keys)
        accumulated_subfolder_size += await _assert_compute_path_size(
            task_manager,
            location_id,
            user_id,
            path=workspace_subfolder,
            expected_total_size=expected_total_size,
            product_name=product_name,
        )

    assert workspace_total_size == accumulated_subfolder_size


async def test_path_compute_size_inexistent_path(
    initialized_app: FastAPI,
    task_manager: TaskManager,
    with_storage_celery_worker: WorkController,
    location_id: LocationID,
    user_id: UserID,
    faker: Faker,
    fake_datcore_tokens: tuple[str, str],
    product_name: ProductName,
):
    await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=Path(faker.file_path(absolute=False)),
        expected_total_size=0,
        product_name=product_name,
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_delete_paths_empty_set(
    initialized_app: FastAPI,
    task_manager: TaskManager,
    with_storage_celery_worker: WorkController,
    user_id: UserID,
    location_id: LocationID,
    product_name: ProductName,
):
    await _assert_delete_paths(
        task_manager,
        location_id,
        user_id,
        product_name,
        paths=set(),
    )


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
            num_nodes=1,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
            workspace_files_count=15,
        )
    ],
    ids=str,
)
async def test_delete_paths(
    initialized_app: FastAPI,
    task_manager: TaskManager,
    with_storage_celery_worker: WorkController,
    user_id: UserID,
    location_id: LocationID,
    with_seeded_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    project_params: ProjectWithFilesParams,
    product_name: ProductName,
):
    assert len(project_params.allowed_file_sizes) == 1, (
        "test preconditions are not filled! allowed file sizes should have only 1 option for this test"
    )
    project, list_of_files = with_seeded_project_with_files

    total_num_files = sum(len(files_in_node) for files_in_node in list_of_files.values())

    # get size of a full project
    expected_total_size = project_params.allowed_file_sizes[0] * total_num_files
    path = Path(project["uuid"])
    await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size,
        product_name=product_name,
    )

    # now select multiple random files to delete
    selected_paths = random.sample(
        list(
            list_of_files[
                NodeID(random.choice(list(project["workbench"])))  # noqa: S311
            ]
        ),
        round(project_params.workspace_files_count / 2),
    )

    await _assert_delete_paths(
        task_manager,
        location_id,
        user_id,
        product_name,
        paths=set({Path(_) for _ in selected_paths}),
    )

    # the size is reduced by the amount of deleted files
    await _assert_compute_path_size(
        task_manager,
        location_id,
        user_id,
        path=path,
        expected_total_size=expected_total_size - len(selected_paths) * project_params.allowed_file_sizes[0],
        product_name=product_name,
    )
