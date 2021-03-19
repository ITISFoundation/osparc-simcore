from dataclasses import dataclass
from typing import Dict, List

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.storage_models import (
    file_meta_data,
    projects,
    user_to_groups,
)
from sqlalchemy.sql import text

ProjectID = str


@dataclass
class AccessRights:
    read: bool
    write: bool
    delete: bool


async def get_projects_access_rights(
    conn: SAConnection, user_id: int
) -> Dict[ProjectID, AccessRights]:
    """ returns rights that user_id has on projects """

    smt = text(
        f"""\
    SELECT uuid, access_rights
    FROM projects
    WHERE (
        jsonb_exists_any( access_rights, (
               SELECT ARRAY( SELECT gid::TEXT FROM user_to_groups WHERE uid = {user_id} )
            )
        )
        OR prj_owner = {user_id}
    )
    """
    )

    projects_access_rights = {}

    async for row in conn.execute(smt):
        prj_access = {"read": False, "write": False, "delete": False}
        for grp_access in row.access_rights.values():
            for key in grp_access:
                prj_access[key] |= grp_access[key]

        assert isinstance(row.uuid, ProjectID)
        projects_access_rights[row.uuid] = AccessRights(**prj_access)
    return projects_access_rights


async def get_readable_project_ids(conn: SAConnection, user_id: int) -> List[ProjectID]:
    projects_access_rights = await get_projects_access_rights(conn, int(user_id))
    return [pid for pid, access in projects_access_rights.items() if access.read]
