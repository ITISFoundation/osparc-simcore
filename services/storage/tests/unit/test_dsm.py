# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from faker import Faker
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from servicelib.utils import limited_gather
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def dsm_mockup_complete_db(
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    upload_file: Callable[
        [ByteSize, str, SimcoreS3FileID | None],
        Awaitable[tuple[Path, SimcoreS3FileID]],
    ],
    cleanup_user_projects_file_metadata: None,
    faker: Faker,
) -> tuple[FileMetaData, FileMetaData]:
    file_size = TypeAdapter(ByteSize).validate_python("10Mib")
    uploaded_files = await limited_gather(
        *(upload_file(file_size, faker.file_name(), None) for _ in range(2)),
        limit=2,
    )
    fmds = await limited_gather(
        *(simcore_s3_dsm.get_file(user_id, file_id) for _, file_id in uploaded_files),
        limit=0,
    )
    assert len(fmds) == 2

    return (fmds[0], fmds[1])
