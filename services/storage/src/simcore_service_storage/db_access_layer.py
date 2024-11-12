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
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from simcore_postgres_database.storage_models import file_meta_data, user_to_groups
from simcore_postgres_database.utils_sql import assemble_array_groups

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccessRights:
    read: bool
    write: bool
    delete: bool

    @classmethod
    def all(cls) -> "AccessRights":
        return cls(read=True, write=True, delete=True)

    @classmethod
    def none(cls) -> "AccessRights":
        return cls(read=False, write=False, delete=False)


class AccessLayerError(Exception):
    """Base class for access-layer related errors"""


class InvalidFileIdentifierError(AccessLayerError):
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
    assert rows is not None  # nosec
    return [g.gid for g in rows]


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


access_rights_subquery = (
    sa.select(
        project_to_groups.c.project_uuid,
        sa.func.jsonb_object_agg(
            project_to_groups.c.gid,
            sa.func.jsonb_build_object(
                "read",
                project_to_groups.c.read,
                "write",
                project_to_groups.c.write,
                "delete",
                project_to_groups.c.delete,
            ),
        )
        .filter(project_to_groups.c.read)  # Filters out entries where "read" is False
        .label("access_rights"),
    ).group_by(project_to_groups.c.project_uuid)
).subquery("access_rights_subquery")


workspace_access_rights_subquery = (
    sa.select(
        workspaces_access_rights.c.workspace_id,
        sa.func.jsonb_object_agg(
            workspaces_access_rights.c.gid,
            sa.func.jsonb_build_object(
                "read",
                workspaces_access_rights.c.read,
                "write",
                workspaces_access_rights.c.write,
                "delete",
                workspaces_access_rights.c.delete,
            ),
        )
        .filter(workspaces_access_rights.c.read)
        .label("access_rights"),
    ).group_by(workspaces_access_rights.c.workspace_id)
).subquery("workspace_access_rights_subquery")


async def list_projects_access_rights(
    conn: SAConnection, user_id: UserID
) -> dict[ProjectID, AccessRights]:
    """
    Returns access-rights of user (user_id) over all OWNED or SHARED projects
    """

    user_group_ids: list[GroupID] = await _get_user_groups_ids(conn, user_id)

    private_workspace_query = (
        sa.select(
            projects.c.uuid,
            access_rights_subquery.c.access_rights,
        )
        .select_from(projects.join(access_rights_subquery, isouter=True))
        .where(
            (
                (projects.c.prj_owner == user_id)
                | sa.text(
                    f"jsonb_exists_any(access_rights_subquery.access_rights, {assemble_array_groups(user_group_ids)})"
                )
            )
            & (projects.c.workspace_id.is_(None))
        )
    )

    shared_workspace_query = (
        sa.select(
            projects.c.uuid,
            workspace_access_rights_subquery.c.access_rights,
        )
        .select_from(
            projects.join(
                workspace_access_rights_subquery,
                projects.c.workspace_id
                == workspace_access_rights_subquery.c.workspace_id,
            )
        )
        .where(
            (
                sa.text(
                    f"jsonb_exists_any(workspace_access_rights_subquery.access_rights, {assemble_array_groups(user_group_ids)})"
                )
            )
            & (projects.c.workspace_id.is_not(None))
        )
    )

    combined_query = sa.union_all(private_workspace_query, shared_workspace_query)

    projects_access_rights = {}

    async for row in conn.execute(combined_query):
        assert isinstance(row.access_rights, dict)  # nosec
        assert isinstance(row.uuid, str)  # nosec

        if row.access_rights:
            # TODO: access_rights should be direclty filtered from result in stm instead calling again user_group_ids
            projects_access_rights[ProjectID(row.uuid)] = _aggregate_access_rights(
                row.access_rights, user_group_ids
            )

        else:
            # backwards compatibility
            # - no access_rights defined BUT project is owned
            projects_access_rights[ProjectID(row.uuid)] = AccessRights.all()

    return projects_access_rights


async def get_project_access_rights(
    conn: SAConnection, user_id: UserID, project_id: ProjectID
) -> AccessRights:
    """
    Returns access-rights of user (user_id) over a project resource (project_id)
    """
    user_group_ids: list[GroupID] = await _get_user_groups_ids(conn, user_id)

    private_workspace_query = (
        sa.select(
            projects.c.prj_owner,
            access_rights_subquery.c.access_rights,
        )
        .select_from(projects.join(access_rights_subquery, isouter=True))
        .where(
            (projects.c.uuid == f"{project_id}")
            & (
                (projects.c.prj_owner == user_id)
                | sa.text(
                    f"jsonb_exists_any(access_rights_subquery.access_rights, {assemble_array_groups(user_group_ids)})"
                )
            )
            & (projects.c.workspace_id.is_(None))
        )
    )

    shared_workspace_query = (
        sa.select(
            projects.c.prj_owner,
            workspace_access_rights_subquery.c.access_rights,
        )
        .select_from(
            projects.join(
                workspace_access_rights_subquery,
                projects.c.workspace_id
                == workspace_access_rights_subquery.c.workspace_id,
            )
        )
        .where(
            (projects.c.uuid == f"{project_id}")
            & (
                sa.text(
                    f"jsonb_exists_any(workspace_access_rights_subquery.access_rights, {assemble_array_groups(user_group_ids)})"
                )
            )
            & (projects.c.workspace_id.is_not(None))
        )
    )

    combined_query = sa.union_all(private_workspace_query, shared_workspace_query)

    result: ResultProxy = await conn.execute(combined_query)
    row: RowProxy | None = await result.first()

    if not row:
        # Either project does not exists OR user_id has NO access
        return AccessRights.none()

    assert row.prj_owner is None or isinstance(row.prj_owner, int)  # nosec
    assert isinstance(row.access_rights, dict)  # nosec

    if row.prj_owner == user_id:
        return AccessRights.all()

    # determine user's access rights by aggregating AR of all groups
    return _aggregate_access_rights(row.access_rights, user_group_ids)


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
                    "File %s references a project that does not exists in db",
                    file_id,
                )
                return AccessRights.none()

        except (ValueError, AttributeError) as err:
            raise InvalidFileIdentifierError(
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
