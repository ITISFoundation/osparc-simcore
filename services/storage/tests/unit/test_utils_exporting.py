import math
import random
from collections.abc import AsyncIterable, Awaitable, Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from models_library.api_schemas_storage import FileUploadSchema
from models_library.projects_nodes_io import SimcoreS3FileID, StorageFileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from simcore_service_storage.constants import LinkType
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from simcore_service_storage.utils.exporting import create_s3_export

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def paths_for_export(
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    populate_directory: Callable[..., Awaitable[set[SimcoreS3FileID]]],
    delete_directory: Callable[..., Awaitable[None]],
) -> AsyncIterable[set[StorageFileID]]:
    dir_name = "data_to_export"

    directory_file_upload: FileUploadSchema = await create_empty_directory(
        dir_name=dir_name
    )

    uploaded_files: set[StorageFileID] = await populate_directory(
        TypeAdapter(ByteSize).validate_python("10MiB"), dir_name, 10, 4
    )

    yield uploaded_files

    await delete_directory(directory_file_upload=directory_file_upload)


def _get_folder_and_files_selection(
    paths_for_export: set[StorageFileID],
) -> list[StorageFileID]:
    # select 10 % of files

    random_files: list[StorageFileID] = [
        random.choice(list(paths_for_export))  # noqa: S311
        for _ in range(math.ceil(0.1 * len(paths_for_export)))
    ]

    all_containing_folders: set[StorageFileID] = {
        TypeAdapter(StorageFileID).validate_python(f"{Path(f).parent}")
        for f in random_files
    }

    element_selection = random_files + list(all_containing_folders)

    # ensure all elements are duplicated and shuffled
    duplicate_selection = [*element_selection, *element_selection]
    random.shuffle(duplicate_selection)  # type: ignore
    return duplicate_selection


async def test_workflow(
    initialized_app: FastAPI,
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    paths_for_export: set[StorageFileID],
):

    selection_to_export = _get_folder_and_files_selection(paths_for_export)

    # TODO: generate some content in S3, both single files and
    # also some folders
    # let's select files form different folders
    # also let's send the same file selected in the same fodler (we avoid path duplication by default)
    # also send over multiple times the same file

    file_id = await create_s3_export(initialized_app, user_id, selection_to_export)

    download_link = await simcore_s3_dsm.create_file_download_link(
        user_id, file_id, LinkType.PRESIGNED
    )

    assert file_id in f"{download_link}"
