from typing import Optional

from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_service_webserver._constants import APP_PROJECT_DBAPI
from simcore_service_webserver.projects._access import (
    AccessRights,
    get_project_access_rights,
)
from simcore_service_webserver.projects.projects_db import ProjectDBAPI


async def test_access_rights(
    client: TestClient, user_id: UserID, project_id: ProjectID
):
    assert client.app

    db: ProjectDBAPI = client.app[APP_PROJECT_DBAPI]

    async with db.engine.acquire() as conn, conn.begin():
        # access layer
        can: Optional[AccessRights] = await get_project_access_rights(
            conn, int(user_id), project_id
        )
        assert not can.read
        assert not can.delete
