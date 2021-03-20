""" Helper functions to determin access-rights on stored data

# DRAFT Rationale:

    osparc-simcore defines TWO authorization methods: i.e. a set of rules on what,
    how and when any resource can be accessed or operated by a user

    ## ROLE-BASED METHOD:
        In this method, a user is assigned a role (user/tester/admin) upon registration. Each role is
        system-wide and defines a set of operations that the user *can* perform
            - Every operation is named as a resource and an action (e.g. )
            - Resource is named hierarchically
            - Roles can inherit permitted operations from other role
        This method is static because is system-wide and it is defined directly in the
        code at services/web/server/src/simcore_service_webserver/security_roles.py
        It is defined on top of every API entrypoint and applied just after authentication of the user.

    ## GROUP-BASED METHOD:
        The second method is designed to share a resource among groups of users dynamically. A group
        defines a set of rules that apply to a resource and users can be added to the group dynamically.
        So far, there are two resources that define access rights (AR):
            - one applies to projects (read/write/delete) and
            - the other to services (execute/write)
        The project access rights are set in the column "access_rights" of the "projects" table .
        The service access rights has its own table: service_access_rights

        Access rights apply hierarchically, meaning that the access granted to a project applies
        to all nodes inside and stored data in nodes.

        How do these two AR coexist?: Access to read, write or delete a project are defined in the project AR but execution
        will depend on the service AR attached to nodes inside.

        What about stored data?
        - data generated in nodes inherits the AR from the associated project
        - data generated in API uses full AR provided by ownership (i.e. user_id in files_meta_data table)

"""


import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.storage_models import file_meta_data
from sqlalchemy.sql import text

from .models import FileMetaData, FileMetaDataEx

logger = logging.getLogger(__name__)


ProjectID = str


@dataclass
class AccessRights:
    read: bool
    write: bool
    delete: bool

    @classmethod
    def all(cls) -> "AccessRights":
        return cls(True, True, True)

    @classmethod
    def none(cls) -> "AccessRights":
        return cls(False, False, False)


class NotAllowedError(Exception):
    ...


async def list_projects_access_rights(
    conn: SAConnection, user_id: int
) -> Dict[ProjectID, AccessRights]:
    """
    Returns access-rights of user (user_id) over all OWNED or SHARED projects
    """

    smt = text(
        f"""\
    SELECT uuid, access_rights
    FROM projects
    WHERE (
        prj_owner = {user_id}
        OR jsonb_exists_any( access_rights, (
               SELECT ARRAY( SELECT gid::TEXT FROM user_to_groups WHERE uid = {user_id} )
            )
        )sql
    )
    """
    )

    projects_access_rights = {}

    async for row in conn.execute(smt):
        assert isinstance(row.access_rights, dict)
        assert isinstance(row.uuid, ProjectID)

        if row.access_rights:
            try:
                prj_access = {"read": False, "write": False, "delete": False}
                for grp_access in row.access_rights.values():
                    for key in grp_access:
                        prj_access[key] |= grp_access[key]

                projects_access_rights[row.uuid] = AccessRights(**prj_access)
            except KeyError:
                # NOTE: database does NOT include schema for json access_rights column!
                logger.warning("Invalid entry in projects.access_rights: %s", row)
        else:
            # backwards compatibility
            # - no access_rights defined BUT project is owned
            projects_access_rights[row.uuid] = AccessRights(
                read=True, write=True, delete=True
            )

    return projects_access_rights


async def get_project_access_rights(
    conn: SAConnection, user_id: int, project_id: UUID
) -> AccessRights:
    """
    Returns access-rights of user (user_id) over a project resource (project_id)
    """

    stmt = text(
        f"""\
        SELECT prj_owner, access_rights
        FROM projects
        WHERE (
            ( uuid = {project_id} ) AND (
                prj_owner = {user_id}
                OR jsonb_exists_any( access_rights, (
                    SELECT ARRAY( SELECT gid::TEXT FROM user_to_groups WHERE uid = {user_id} )
                    )
                )
            )
        )
        """
    )

    result: ResultProxy = await conn.execute(stmt)
    row: Optional[RowProxy] = await result.first()

    if not row:
        # Either project does not exists OR user_id has NO access
        return AccessRights.none()

    assert isinstance(row.prj_owner, int)
    assert isinstance(row.access_rights, dict)

    if row.prj_owner == user_id:
        return AccessRights.all()
    return AccessRights(**dict(row.access_rights))


async def get_file_access_rights(
    conn: SAConnection, user_id: int, file_uuid: str
) -> AccessRights:
    """
    Returns access-rights of user (user_id) over data file resource (file_uuid)
    """

    stmt = sa.select([file_meta_data.c.project_id, file_meta_data.c.user_id]).where(
        file_meta_data.c.file_uuid == file_uuid
    )
    result: ResultProxy = await conn.execute(stmt)
    row: Optional[RowProxy] = await result.first()

    if row:
        if row.user_id == user_id:
            # is owner
            return AccessRights.all()

        if not row.project_id:
            return AccessRights.none()

        # has associated project, then use
        access_rights = await get_project_access_rights(
            conn, user_id, project_id=row.project_id
        )
        if not access_rights:
            logger.warning(
                "File %s references a project %s that does not exists in db",
                file_uuid,
                row.project_id,
            )
            return AccessRights.none()

        return access_rights

    else:
        # file is not registered in meta-data table (e.g. is about to be uploaded or it was deleted)
        try:
            parent, _, _ = file_uuid.split("/")

            if parent == "api":
                # ownership still not defined
                return AccessRights.all()

            else:
                access_rights = await get_project_access_rights(
                    conn, user_id, project_id=UUID(parent)
                )
                if not access_rights:
                    logger.warning(
                        "File %s references a project %s that does not exists in db",
                        file_uuid,
                        row.project_id,
                    )
                    return AccessRights.none()

                return access_rights

        except (ValueError, AttributeError) as err:
            raise ValueError(
                f"Invalid file_uuid. '{file_uuid}' does not follow any known pattern ({err})"
            ) from err


# HELPERS -----------------------------------------------


async def get_readable_project_ids(conn: SAConnection, user_id: int) -> List[ProjectID]:
    """ Returns a list of projects where user has granted read-access """
    projects_access_rights = await list_projects_access_rights(conn, int(user_id))
    return [pid for pid, access in projects_access_rights.items() if access.read]


# FILEMETADATA repository ----------------------------
#
#


async def list_files_metadata(conn: SAConnection, user_id: int) -> List[FileMetaDataEx]:
    files_meta = deque()

    # filter accounting AR
    can_read_projects = await get_readable_project_ids(conn, int(user_id))

    query = sa.select([file_meta_data]).where(
        (file_meta_data.c.user_id == user_id)
        | file_meta_data.c.project_id.in_(can_read_projects)
    )
    logger.debug("user %s query: %s", user_id, query)

    # list
    async for row in conn.execute(query):
        d = FileMetaData(**dict(row))
        dex = FileMetaDataEx(fmd=d, parent_id=str(Path(d.object_name).parent))
        files_meta.append(dex)

    return list(files_meta)
