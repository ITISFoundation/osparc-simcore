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
        The second method is designed to dynamically share a resource among groups of users. A group
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
from dataclasses import dataclass

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.projects import ProjectID
from models_library.projects_nodes_io import StorageFileID
from models_library.users import GroupID, UserID
from simcore_postgres_database.storage_models import file_meta_data, user_to_groups
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)


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


class AccessLayerError(Exception):
    """Base class for access-layer related errors"""


class InvalidFileIdentifier(AccessLayerError):
    """Identifier does not follow the criteria to
    be a file identifier (see naming criteria below)
    """

    def __init__(self, identifier, reason=None, details=None):
        self.identifier = identifier
        self.reason = reason or "Invalid file identifier"
        self.details = details

        super().__init__(self.reason, self.details)

    def __str__(self):
        return f"Error in {self.identifier}: {self.reason} [{self.details}]"


async def _get_user_groups_ids(conn: SAConnection, user_id: UserID) -> list[GroupID]:
    stmt = sa.select(user_to_groups.c.gid).where(user_to_groups.c.uid == user_id)
    rows = await (await conn.execute(stmt)).fetchall()
    user_group_ids = [g.gid for g in rows]
    return user_group_ids


def _aggregate_access_rights(
    access_rights: dict[str, dict], group_ids: list[GroupID]
) -> AccessRights:
    try:
        prj_access = {"read": False, "write": False, "delete": False}
        for gid, grp_access in access_rights.items():
            if int(gid) in group_ids:
                for operation in grp_access:
                    prj_access[operation] |= grp_access[operation]

        return AccessRights(**prj_access)
    except KeyError:
        # NOTE: database does NOT include schema for json access_rights column!
        logger.warning(
            "Invalid entry in projects.access_rights. Revoking all rights [%s]",
            access_rights,
        )
        return AccessRights.none()


async def list_projects_access_rights(
    conn: SAConnection, user_id: UserID
) -> dict[ProjectID, AccessRights]:
    """
    Returns access-rights of user (user_id) over all OWNED or SHARED projects
    """

    user_group_ids: list[int] = await _get_user_groups_ids(conn, user_id)

    smt = text(
        f"""\
    SELECT uuid, access_rights
    FROM projects
    WHERE (
        prj_owner = {user_id}
        OR jsonb_exists_any( access_rights, (
               SELECT ARRAY( SELECT gid::TEXT FROM user_to_groups WHERE uid = {user_id} )
            )
        )
    )
    """
    )
    projects_access_rights = {}

    async for row in conn.execute(smt):
        assert isinstance(row.access_rights, dict)  # nosec
        assert isinstance(row.uuid, str)  # nosec

        if row.access_rights:
            # TODO: access_rights should be direclty filtered from result in stm instead calling again user_group_ids
            projects_access_rights[row.uuid] = _aggregate_access_rights(
                row.access_rights, user_group_ids
            )

        else:
            # backwards compatibility
            # - no access_rights defined BUT project is owned
            projects_access_rights[row.uuid] = AccessRights.all()

    return projects_access_rights


async def get_project_access_rights(
    conn: SAConnection, user_id: UserID, project_id: ProjectID
) -> AccessRights:
    """
    Returns access-rights of user (user_id) over a project resource (project_id)
    """
    user_group_ids: list[int] = await _get_user_groups_ids(conn, user_id)

    stmt = text(
        f"""\
        SELECT prj_owner, access_rights
        FROM projects
        WHERE (
            ( uuid = '{project_id}' ) AND (
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
    row: RowProxy | None = await result.first()

    if not row:
        # Either project does not exists OR user_id has NO access
        return AccessRights.none()

    assert row.prj_owner is None or isinstance(row.prj_owner, int)  # nosec
    assert isinstance(row.access_rights, dict)  # nosec

    if row.prj_owner == user_id:
        return AccessRights.all()

    # determine user's access rights by aggregating AR of all groups
    prj_access = _aggregate_access_rights(row.access_rights, user_group_ids)
    return prj_access


async def get_file_access_rights(
    conn: SAConnection, user_id: UserID, file_id: StorageFileID
) -> AccessRights:
    """
    Returns access-rights of user (user_id) over data file resource (file_id)

    raises InvalidFileIdentifier
    """

    #
    # 1. file registered in file_meta_data table
    #
    stmt = sa.select(file_meta_data.c.project_id, file_meta_data.c.user_id).where(
        file_meta_data.c.file_id == f"{file_id}"
    )
    result: ResultProxy = await conn.execute(stmt)
    row: RowProxy | None = await result.first()

    if row:
        if int(row.user_id) == user_id:
            # is owner
            return AccessRights.all()

        if not row.project_id:
            # not owner and not shared via project
            return AccessRights.none()

        # has associated project
        access_rights = await get_project_access_rights(
            conn, user_id, project_id=row.project_id
        )
        if not access_rights:
            logger.warning(
                "File %s references a project %s that does not exists in db."
                "TIP: Audit sync between files_meta_data and projects tables",
                file_id,
                row.project_id,
            )
            return AccessRights.none()

    else:
        #
        # 2. file is NOT registered in meta-data table e.g. it is about to be uploaded or it was deleted
        #    We rely on the assumption that file_id is formatted either as
        #
        #       - project's data: {project_id}/{node_id}/{filename/with/possible/folders}
        #       - API data:       api/{file_id}/{filename/with/possible/folders}
        #
        try:
            parent, _, _ = file_id.split("/", maxsplit=2)

            if parent == "api":
                # FIXME: this is wrong, all api data must be registered and OWNED
                # ownership still not defined, so we assume it is user_id
                return AccessRights.all()

            # otherwise assert 'parent' string corresponds to a valid UUID
            access_rights = await get_project_access_rights(
                conn, user_id, project_id=ProjectID(parent)
            )
            if not access_rights:
                logger.warning(
                    "File %s references a project %s that does not exists in db",
                    file_id,
                    row.project_id,
                )
                return AccessRights.none()

        except (ValueError, AttributeError) as err:
            raise InvalidFileIdentifier(
                identifier=file_id,
                details=str(err),
            ) from err

    return access_rights


# HELPERS -----------------------------------------------


async def get_readable_project_ids(
    conn: SAConnection, user_id: UserID
) -> list[ProjectID]:
    """Returns a list of projects where user has granted read-access"""
    projects_access_rights = await list_projects_access_rights(conn, user_id)
    return [pid for pid, access in projects_access_rights.items() if access.read]
