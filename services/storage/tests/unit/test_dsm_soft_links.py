# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import AsyncIterator

import attr
import pytest
from aiopg.sa.engine import Engine
from simcore_service_storage.constants import SIMCORE_S3_STR
from simcore_service_storage.dsm import DataStorageManager
from simcore_service_storage.models import FileMetaData, FileMetaDataEx, file_meta_data
from simcore_service_storage.utils import create_resource_uuid
from sqlalchemy.sql.expression import literal_column

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["minio"]


@pytest.fixture
def storage(aiopg_engine: Engine) -> DataStorageManager:

    return DataStorageManager(
        s3_client=None,
        engine=aiopg_engine,
        loop=None,
        pool=None,
        simcore_bucket_name="master-simcore",
        has_project_db=True,
        app=None,
    )  # type: ignore


@pytest.fixture()
async def output_file(
    user_id: int, project_id: str, aiopg_engine: Engine
) -> AsyncIterator[FileMetaData]:

    node_id = "fd6f9737-1988-341b-b4ac-0614b646fa82"

    # pylint: disable=no-value-for-parameter

    file = FileMetaData()
    file.simcore_from_uuid(
        f"{project_id}/{node_id}/filename.txt", bucket_name="master-simcore"
    )
    file.entity_tag = "df9d868b94e53d18009066ca5cd90e9f"
    file.file_size = 12
    file.user_name = "test"
    file.user_id = str(user_id)

    async with aiopg_engine.acquire() as conn:
        stmt = (
            file_meta_data.insert()
            .values(
                **attr.asdict(file),
            )
            .returning(literal_column("*"))
        )
        result = await conn.execute(stmt)
        row = await result.fetchone()

        # hacks defect
        file.user_id = str(user_id)
        file.location_id = str(file.location_id)
        # --
        assert file == FileMetaData(**dict(row))  # type: ignore

        yield file

        result = await conn.execute(
            file_meta_data.delete().where(file_meta_data.c.file_uuid == row.file_uuid)
        )


async def test_create_soft_link(
    storage: DataStorageManager, user_id: int, output_file: FileMetaData
):

    api_file_id = create_resource_uuid(
        output_file.project_id, output_file.node_id, output_file.file_name
    )
    file_name = output_file.file_name

    link_file: FileMetaDataEx = await storage.create_soft_link(
        user_id, output_file.file_uuid, f"api/{api_file_id}/{file_name}"
    )
    assert isinstance(link_file, FileMetaDataEx)
    assert isinstance(link_file.fmd, FileMetaData)

    # copy:
    #     - you have two different versions of the file.
    #     - if you edit one, the other one stays the same.
    #     - if you delete one, the other one stays there, but it may not be identical if it was edited
    #     - twice as much disk space used (two different files)
    # hard link:
    #     - you have one file with two different filenames.
    #     - If you edit one, it gets edited in all filename locations
    #     - if you delete one, it still exists in other places
    #     - only one file on disk
    # soft link:
    #     - you have one file with one filename and a pointer to that file with the other filename.
    #     - if you edit the link its really editing the original file
    #     - if you delete the file the link is broken
    #     - if you remove the link the file stays in place.
    #     - only one file on disk
    #
    #
    #
    # 6686134 -rw-rw-r--  1 crespo crespo 1371 Apr 14 14:53 TODO.md
    # 6686594 -rw-rw-r--  2 crespo crespo    6 Mar  9  2020 VERSION
    # 6686594 -rw-rw-r--  2 crespo crespo    6 Mar  9  2020 VERSION-hard
    # 6686197 lrwxrwxrwx  1 crespo crespo    7 Apr 14 14:48 VERSION-link -> VERSION

    assert link_file.fmd.file_uuid == f"api/{api_file_id}/{file_name}"
    assert link_file.fmd.file_id == link_file.fmd.file_uuid
    assert link_file.fmd.object_name == output_file.object_name
    assert link_file.fmd.entity_tag == output_file.entity_tag
    assert link_file.fmd.is_soft_link

    # TODO: in principle we keep this ...
    # assert output_file.created_at < link_file.fmd.created_at
    # assert output_file.last_modified < link_file.fmd.last_modified

    # can find
    files_list = await storage.search_files_starting_with(
        user_id, f"api/{api_file_id}/{file_name}"
    )
    assert len(files_list) == 1
    assert files_list[0] == link_file

    # can get
    got_file = await storage.list_file(
        str(user_id), SIMCORE_S3_STR, f"api/{api_file_id}/{file_name}"
    )

    assert got_file == link_file
