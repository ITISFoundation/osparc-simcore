# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeAlias

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from fastapi_pagination.cursor import CursorPage
from models_library.api_schemas_storage.storage_schemas import PathMetaDataGet
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from pytest_simcore.helpers.storage_utils import FileIDDict, ProjectWithFilesParams

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]

_IsFile: TypeAlias = bool


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


async def _assert_list_paths(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    *,
    file_filter: Path | None,
    limit: int = 25,
    expected_paths: list[tuple[Path, _IsFile]],
    check_total: bool = True,
) -> CursorPage[PathMetaDataGet]:
    offset = 0
    total_expected = len(expected_paths)
    next_cursor = 0  # NOTE: this will initialize
    total_received = 0
    while next_cursor is not None:
        url = url_from_operation_id(
            client, initialized_app, "list_paths", location_id=f"{location_id}"
        ).with_query(
            user_id=user_id,
            size=limit,
        )
        if next_cursor:
            url = url.update_query(cursor=next_cursor)

        if file_filter is not None:
            url = url.update_query(file_filter=f"{file_filter}")
        response = await client.get(f"{url}")

        page_of_files, _ = assert_status(
            response,
            status.HTTP_200_OK,
            CursorPage[PathMetaDataGet],
            expect_envelope=False,
        )
        assert page_of_files
        assert len(page_of_files.items) == min(limit, total_expected - offset)

        for (expected_path, is_file), received_path in zip(
            expected_paths[offset : offset + limit], page_of_files.items, strict=True
        ):
            assert received_path.path == expected_path
            if is_file:
                assert received_path.file_meta_data is not None
            else:
                assert received_path.file_meta_data is None

        if check_total:
            assert page_of_files.total == total_expected
        else:
            assert page_of_files.total is None
        next_cursor = page_of_files.next_page
        total_received += len(page_of_files.items)
        offset += limit
    assert total_received == total_expected
    assert page_of_files.next_page is None
    return page_of_files


async def test_list_paths_root_folder_of_empty_returns_nothing(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
):
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=None,
        expected_paths=[],
    )


@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=10,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
            workspace_files_count=10,
        )
    ],
    ids=str,
)
async def test_list_paths_pagination(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
    ],
    faker: Faker,
):
    project, list_of_files = with_random_project_with_files
    num_nodes = len(list(project["workbench"]))

    # ls the nodes (DB-based)
    file_filter = Path(project["uuid"])
    expected_paths = sorted(
        ((file_filter / node_key, False) for node_key in project["workbench"]),
        key=lambda x: x[0],
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=file_filter,
        expected_paths=expected_paths,
        limit=int(num_nodes / 2 + 0.5),
    )

    # ls in the workspace (S3-based)
    # ls in the workspace
    selected_node_id = NodeID(random.choice(list(project["workbench"])))  # noqa: S311
    selected_node_s3_keys = [
        Path(s3_object_id) for s3_object_id in list_of_files[selected_node_id]
    ]
    workspace_file_filter = file_filter / f"{selected_node_id}" / "workspace"
    expected_paths = _filter_and_group_paths_one_level_deeper(
        selected_node_s3_keys, workspace_file_filter
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=workspace_file_filter,
        expected_paths=expected_paths,
        limit=1,
    )
    # ls in until we get to some files
    while selected_subfolders := [p for p in expected_paths if p[1] is False]:
        selected_path_filter = random.choice(selected_subfolders)  # noqa: S311
        expected_paths = _filter_and_group_paths_one_level_deeper(
            selected_node_s3_keys, selected_path_filter[0]
        )
        await _assert_list_paths(
            initialized_app,
            client,
            location_id,
            user_id,
            file_filter=selected_path_filter[0],
            expected_paths=expected_paths,
        )


@pytest.mark.parametrize(
    "project_params, num_projects",
    [
        (
            ProjectWithFilesParams(
                num_nodes=3,
                allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
                workspace_files_count=10,
            ),
            3,
        )
    ],
    ids=str,
)
async def test_list_paths(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    project_params: ProjectWithFilesParams,
    num_projects: int,
):
    project_to_files_mapping = [
        await random_project_with_files(project_params) for _ in range(num_projects)
    ]
    project_to_files_mapping.sort(key=lambda x: x[0]["uuid"])

    # ls root returns our projects
    expected_paths = sorted(
        ((Path(f"{prj_db['uuid']}"), False) for prj_db, _ in project_to_files_mapping),
        key=lambda x: x[0],
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=None,
        expected_paths=expected_paths,
    )

    # ls with only some part of the path should return only the projects that match
    selected_project, selected_project_files = random.choice(  # noqa: S311
        project_to_files_mapping
    )
    partial_file_filter = Path(
        selected_project["uuid"][: len(selected_project["uuid"]) // 2]
    )
    partial_expected_paths = [
        p for p in expected_paths if f"{p[0]}".startswith(f"{partial_file_filter}")
    ]

    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=partial_file_filter,
        expected_paths=partial_expected_paths,
    )

    # now we ls inside one of the projects returns the nodes
    file_filter = Path(selected_project["uuid"])
    expected_paths = sorted(
        ((file_filter / node_key, False) for node_key in selected_project["workbench"]),
        key=lambda x: x[0],
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=file_filter,
        expected_paths=expected_paths,
    )

    # now we ls in one of the nodes
    selected_node_id = NodeID(
        random.choice(list(selected_project["workbench"]))  # noqa: S311
    )
    selected_node_s3_keys = [
        Path(s3_object_id) for s3_object_id in selected_project_files[selected_node_id]
    ]
    file_filter = file_filter / f"{selected_node_id}"
    expected_node_files = _filter_and_group_paths_one_level_deeper(
        selected_node_s3_keys,
        file_filter,
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=file_filter,
        expected_paths=expected_node_files,
    )

    # ls in the outputs will list 1 entry which is a folder
    node_outputs_file_filter = file_filter / "outputs"
    expected_paths = _filter_and_group_paths_one_level_deeper(
        selected_node_s3_keys, node_outputs_file_filter
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=node_outputs_file_filter,
        expected_paths=expected_paths,
    )

    # ls in output_3 shall reveal the file
    node_outputs_file_filter = file_filter / "outputs" / "output_3"
    expected_paths = _filter_and_group_paths_one_level_deeper(
        selected_node_s3_keys, node_outputs_file_filter
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=node_outputs_file_filter,
        expected_paths=expected_paths,
    )

    # ls in the workspace
    workspace_file_filter = file_filter / "workspace"
    expected_paths = _filter_and_group_paths_one_level_deeper(
        selected_node_s3_keys, workspace_file_filter
    )
    await _assert_list_paths(
        initialized_app,
        client,
        location_id,
        user_id,
        file_filter=workspace_file_filter,
        expected_paths=expected_paths,
        check_total=False,
    )
    # ls in until we get to some files
    while selected_subfolders := [p for p in expected_paths if p[1] is False]:
        selected_path_filter = random.choice(selected_subfolders)  # noqa: S311
        expected_paths = _filter_and_group_paths_one_level_deeper(
            selected_node_s3_keys, selected_path_filter[0]
        )
        await _assert_list_paths(
            initialized_app,
            client,
            location_id,
            user_id,
            file_filter=selected_path_filter[0],
            expected_paths=expected_paths,
            check_total=False,
        )
