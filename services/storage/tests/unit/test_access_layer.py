# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Iterable
from uuid import UUID

import pytest
from aiopg.sa.engine import Engine
from simcore_service_storage.access_layer import (
    AccessRights,
    get_file_access_rights,
    get_project_access_rights,
)

pytest_simcore_core_services_selection = ["postgres"]


@pytest.fixture
async def filemeta_id(
    user_id: int, project_id: str, aiopg_engine: Engine
) -> Iterable[str]:
    raise NotImplementedError()


async def test_access_rights_on_owned_project(
    user_id: int, project_id: UUID, aiopg_engine: Engine
):

    async with aiopg_engine.acquire() as conn:

        access = await get_project_access_rights(conn, user_id, str(project_id))
        assert access == AccessRights.all()

        # still NOT registered in file_meta_data BUT with prefix {project_id} owned by user
        access = await get_file_access_rights(
            conn, user_id, f"{project_id}/node_id/not-in-file-metadata-table.txt"
        )
        assert access == AccessRights.all()
