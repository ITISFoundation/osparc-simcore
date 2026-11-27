"""Helper functions to determine access-rights on stored data

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

        How do these two AR coexist?: Access to read, write or delete a project are
        defined in the project AR but execution will depend on the service AR attached
        to nodes inside.

        What about stored data?
        - data generated in nodes inherits the AR from the associated project
        - data generated in API uses full AR provided by ownership (i.e. user_id in files_meta_data table)

"""

import logging
from pathlib import PurePosixPath
from typing import Annotated, Final, NamedTuple

import sqlalchemy as sa
from annotated_types import doc
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from simcore_postgres_database.storage_models import file_meta_data, user_to_groups
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ...constants import API_S3_PREFIX, EXPORTS_S3_PREFIX
from ...exceptions.errors import InvalidFileIdentifierError
from ...models import AccessRights
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class _RegisteredDirectory(NamedTuple):
    user_id: UserID
    project_id: ProjectID | None


_ROOT_PARENTS_TO_DROP: Final[
    Annotated[int, doc("trailing `parents` entries: the `api` prefix and the relative root `.`, no directory")]
] = 2


def _ancestor_prefixes(file_id: str) -> list[str]:
    """Prefix of every ancestor directory of file_id, direct parent first

    Analogous to PurePath.parents: every ancestor, not only the direct parent.
    Directory ids end with a slash, which PurePosixPath absorbs into the path
    itself; include it then, so a directory registered without the trailing
    slash still matches.
    """
    path = PurePosixPath(file_id)
    prefixes = [path, *path.parents] if file_id.endswith("/") else list(path.parents)
    return [f"{p}" for p in prefixes[:-_ROOT_PARENTS_TO_DROP]]


async def _get_registered_directories(
    connection: AsyncConnection, stored_file_ids: list[str]
) -> dict[str, _RegisteredDirectory]:
    """Entries registered under any of stored_file_ids, keyed by stored file_id.
    A directory accepts both forms of a prefix, with and without trailing slash.
    """
    if not stored_file_ids:
        return {}
    result = await connection.execute(
        sa.select(file_meta_data.c.file_id, file_meta_data.c.user_id, file_meta_data.c.project_id).where(
            file_meta_data.c.file_id.in_(stored_file_ids)
        )
    )
    return {
        row.file_id: _RegisteredDirectory(
            user_id=UserID(row.user_id),
            project_id=ProjectID(row.project_id) if row.project_id else None,
        )
        for row in result.fetchall()
    }


async def _has_registered_descendants_by_others(connection: AsyncConnection, *, file_id: str, user_id: UserID) -> bool:
    """True if another user has entries registered as descendants of file_id, i.e.
    at paths starting with `file_id/`: file_id is matched as a directory path prefix
    """
    result = await connection.execute(
        sa.select(sa.literal(1))
        .select_from(file_meta_data)
        .where(
            file_meta_data.c.file_id.startswith(f"{file_id.rstrip('/')}/", autoescape=True),
            file_meta_data.c.user_id != user_id,
        )
        .limit(1)
    )
    return result.first() is not None


async def _has_descendants_the_caller_cannot_delete(
    connection: AsyncConnection, *, file_id: str, user_id: UserID
) -> bool:
    """True if a descendant entry of file_id, i.e. at a path starting with
    `file_id/` (file_id as directory prefix), denies the caller delete rights:
    owned by someone else without a project, or shared through a project the
    caller cannot delete. The project rights mirror `get_project_access_rights`,
    owner override included: the override applies only on top of a readable group
    grant, so a caller whose grants were revoked has no rights even as project
    owner.
    """
    user_group_ids = sa.select(user_to_groups.c.gid).where(user_to_groups.c.uid == user_id).scalar_subquery()
    private_grants = sa.select(sa.literal(1)).where(
        (project_to_groups.c.project_uuid == projects.c.uuid)
        & project_to_groups.c.read
        & project_to_groups.c.gid.in_(user_group_ids)
    )
    shared_workspace_grants = sa.select(sa.literal(1)).where(
        (workspaces_access_rights.c.workspace_id == projects.c.workspace_id)
        & workspaces_access_rights.c.read
        & workspaces_access_rights.c.gid.in_(user_group_ids)
    )
    caller_can_read_project = sa.or_(
        sa.and_(projects.c.workspace_id.is_(None), sa.exists(private_grants)),
        sa.and_(projects.c.workspace_id.is_not(None), sa.exists(shared_workspace_grants)),
    )
    caller_can_delete_project = sa.and_(
        caller_can_read_project,
        sa.or_(
            projects.c.prj_owner == user_id,
            sa.and_(
                projects.c.workspace_id.is_(None),
                sa.exists(private_grants.where(project_to_groups.c.delete)),
            ),
            sa.and_(
                projects.c.workspace_id.is_not(None),
                sa.exists(shared_workspace_grants.where(workspaces_access_rights.c.delete)),
            ),
        ),
    )
    result = await connection.execute(
        sa.select(sa.literal(1))
        .select_from(file_meta_data)
        .where(
            file_meta_data.c.file_id.startswith(f"{file_id.rstrip('/')}/", autoescape=True),
            file_meta_data.c.user_id != user_id,
            sa.or_(
                file_meta_data.c.project_id.is_(None),
                ~sa.exists(
                    sa.select(sa.literal(1))
                    .select_from(projects)
                    .where(projects.c.uuid == file_meta_data.c.project_id, caller_can_delete_project)
                ),
            ),
        )
        .limit(1)
    )
    return result.first() is not None


async def _get_user_groups_ids(connection: AsyncConnection, user_id: UserID) -> list[GroupID]:
    stmt = sa.select(user_to_groups.c.gid).where(user_to_groups.c.uid == user_id)
    rows = (await connection.execute(stmt)).fetchall()
    assert rows is not None  # nosec
    return [g.gid for g in rows]


def _aggregate_access_rights(access_rights: dict[str, dict], group_ids: list[GroupID]) -> AccessRights:
    try:
        prj_access = {"read": False, "write": False, "delete": False}
        for gid, grp_access in access_rights.items():
            if int(gid) in group_ids:
                for operation in grp_access:
                    prj_access[operation] |= grp_access[operation]

        return AccessRights(**prj_access)
    except KeyError:
        # NOTE: database does NOT include schema for json access_rights column!
        _logger.warning(
            "Invalid access-rights entry aggregated from project_to_groups. Revoking all rights [%s]",
            access_rights,
        )
        return AccessRights.none()


def my_private_workspace_access_rights_subquery(user_group_ids: list[GroupID]):
    return (
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
            ).label("access_rights"),
        )
        .where(
            (project_to_groups.c.read)  # Filters out entries where "read" is False
            & (project_to_groups.c.gid.in_(user_group_ids))  # Filters gid to be in user_groups
        )
        .group_by(project_to_groups.c.project_uuid)
    ).subquery("my_access_rights_subquery")


def my_shared_workspace_access_rights_subquery(user_group_ids: list[GroupID]):
    return (
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
            ).label("access_rights"),
        )
        .where(
            (workspaces_access_rights.c.read)  # Filters out entries where "read" is False
            & (workspaces_access_rights.c.gid.in_(user_group_ids))  # Filters gid to be in user_groups
        )
        .group_by(workspaces_access_rights.c.workspace_id)
    ).subquery("my_workspace_access_rights_subquery")


def readable_project_ids_stmt(user_id: UserID, product_name: ProductName) -> sa.sql.CompoundSelect:
    user_group_ids = sa.select(user_to_groups.c.gid).where(user_to_groups.c.uid == user_id).scalar_subquery()

    private_access_exists = sa.exists(
        sa.select(sa.literal(1)).where(
            (project_to_groups.c.project_uuid == projects.c.uuid)
            & (project_to_groups.c.read)
            & (project_to_groups.c.gid.in_(user_group_ids))
        )
    )

    private_workspace_query = (
        sa.select(projects.c.uuid)
        .select_from(projects)
        .where((projects.c.workspace_id.is_(None)) & (projects.c.product_name == product_name) & private_access_exists)
    )

    shared_access_exists = sa.exists(
        sa.select(sa.literal(1)).where(
            (workspaces_access_rights.c.workspace_id == projects.c.workspace_id)
            & (workspaces_access_rights.c.read)
            & (workspaces_access_rights.c.gid.in_(user_group_ids))
        )
    )

    shared_workspace_query = (
        sa.select(projects.c.uuid)
        .select_from(projects)
        .where(
            (projects.c.workspace_id.is_not(None)) & (projects.c.product_name == product_name) & shared_access_exists
        )
    )

    return sa.union_all(private_workspace_query, shared_workspace_query)


async def _list_user_projects_access_rights_with_read_access(
    connection: AsyncConnection, user_id: UserID, product_name: ProductName
) -> list[ProjectID]:
    """
    Returns access-rights of user (user_id) over all OWNED or SHARED projects
    """
    combined_query = readable_project_ids_stmt(user_id, product_name)

    projects_access_rights = []

    async for row in await connection.stream(combined_query):
        assert isinstance(row.uuid, str)  # nosec

        projects_access_rights.append(ProjectID(row.uuid))

    return projects_access_rights


class AccessLayerRepository(BaseRepository):
    async def get_project_access_rights(
        self,
        *,
        connection: AsyncConnection | None = None,
        user_id: UserID,
        project_id: ProjectID,
    ) -> AccessRights:
        """
        Returns access-rights of user (user_id) over a project resource (project_id)
        """

        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            user_group_ids = await _get_user_groups_ids(conn, user_id)
            _my_access_rights_subquery = my_private_workspace_access_rights_subquery(user_group_ids)

            private_workspace_query = (
                sa.select(
                    projects.c.prj_owner,
                    _my_access_rights_subquery.c.access_rights,
                )
                .select_from(projects.join(_my_access_rights_subquery))
                .where((projects.c.uuid == f"{project_id}") & (projects.c.workspace_id.is_(None)))
            )

            _my_workspace_access_rights_subquery = my_shared_workspace_access_rights_subquery(user_group_ids)

            shared_workspace_query = (
                sa.select(
                    projects.c.prj_owner,
                    _my_workspace_access_rights_subquery.c.access_rights,
                )
                .select_from(
                    projects.join(
                        _my_workspace_access_rights_subquery,
                        projects.c.workspace_id == _my_workspace_access_rights_subquery.c.workspace_id,
                    )
                )
                .where((projects.c.uuid == f"{project_id}") & (projects.c.workspace_id.is_not(None)))
            )

            combined_query = sa.union_all(private_workspace_query, shared_workspace_query)
            result = await conn.execute(combined_query)
            row = result.one_or_none()

        if not row:
            # Either project does not exists OR user_id has NO access
            return AccessRights.none()

        assert row.prj_owner is None or isinstance(row.prj_owner, int)  # nosec
        assert isinstance(row.access_rights, dict)  # nosec

        if row.prj_owner == user_id:
            return AccessRights.all()

        # determine user's access rights by aggregating AR of all groups
        return _aggregate_access_rights(row.access_rights, user_group_ids)

    async def _get_access_from_metadata_entry(
        self,
        *,
        connection: AsyncConnection | None,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> AccessRights | None:
        #
        # 1. file registered in file_meta_data table
        #
        stmt = sa.select(file_meta_data.c.project_id, file_meta_data.c.user_id).where(
            file_meta_data.c.file_id == f"{file_id}"
        )
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(stmt)
            row = result.one_or_none()

        if not row:
            return None

        if int(row.user_id) == user_id:
            # is owner
            return AccessRights.all()

        if not row.project_id:
            # not owner and not shared via project
            return AccessRights.none()

        # has associated project
        access_rights = await self.get_project_access_rights(user_id=user_id, project_id=row.project_id)
        if not access_rights:
            _logger.warning(
                "File %s references a project %s that does not exists in db. "
                " TIP: Audit sync between files_meta_data and projects tables",
                file_id,
                row.project_id,
            )
            return AccessRights.none()

        return access_rights

    async def _get_api_data_access_rights(
        self,
        *,
        connection: AsyncConnection | None,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> AccessRights:
        ancestor_prefixes = _ancestor_prefixes(file_id)
        candidates = [p for prefix in ancestor_prefixes for p in (prefix, f"{prefix}/")]

        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            registered_by_file_id = await _get_registered_directories(conn, candidates)
            for prefix in ancestor_prefixes:
                group = [d for key in (prefix, f"{prefix}/") if (d := registered_by_file_id.get(key)) is not None]
                if not group:
                    continue
                if len({(d.user_id, d.project_id) for d in group}) > 1:
                    _logger.warning(
                        "file_meta_data holds conflicting entries for %s and %s/, revoking all rights",
                        prefix,
                        prefix,
                    )
                    return AccessRights.none()
                access_rights = await self._access_rights_of_registered_directory(
                    connection=conn, user_id=user_id, directory=group[0]
                )
                if (access_rights.write or access_rights.delete) and await _has_descendants_the_caller_cannot_delete(
                    conn, file_id=file_id, user_id=user_id
                ):
                    # deleting this path cascades into entries the caller cannot delete
                    # on their own, and so does an upload: create_file_upload_links
                    # deletes the target id (enforcing only write) before storing the
                    # new object. Read does not cascade and is kept.
                    return AccessRights(read=access_rights.read, write=False, delete=False)
                return access_rights

            # deleting an unregistered id cascades to everything below it, so a path
            # populated by other users is not up for grabs
            if await _has_registered_descendants_by_others(conn, file_id=file_id, user_id=user_id):
                return AccessRights.none()
            return AccessRights.all()

    async def _access_rights_of_registered_directory(
        self,
        *,
        connection: AsyncConnection | None,
        user_id: UserID,
        directory: _RegisteredDirectory,
    ) -> AccessRights:
        if int(directory.user_id) == user_id:
            return AccessRights.all()
        if not directory.project_id:
            return AccessRights.none()
        return await self.get_project_access_rights(
            connection=connection, user_id=user_id, project_id=directory.project_id
        )

    @staticmethod
    def _get_exports_access_rights(*, user_id: UserID, sub_path: str) -> AccessRights:
        """The owner of an exports/ path is embedded in it: exports/{user_id}/{filename}

        NOTE: all permissions are required for: downloading, uploading and aborting
        """
        path_owner_id = sub_path.split("/", maxsplit=1)[0]
        return AccessRights.all() if int(path_owner_id) == user_id else AccessRights.none()

    async def _get_access_without_metadata_entry(
        self,
        *,
        connection: AsyncConnection | None,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> AccessRights:
        #
        # 2. file is NOT registered in meta-data table e.g. it is about to be uploaded or it was deleted
        #    We rely on the assumption that file_id is formatted either as
        #
        #       - project's data: {project_id}/{node_id}/{filename/with/possible/folders}
        #       - API data:       api/{file_id}/{filename/with/possible/folders}
        #       - Exporter data:  exporter/{user_id}/{filename/with/possible/folders}
        #

        try:
            root_folder, sub_path = file_id.split("/", maxsplit=1)

            if root_folder == API_S3_PREFIX:
                return await self._get_api_data_access_rights(connection=connection, user_id=user_id, file_id=file_id)

            if root_folder == EXPORTS_S3_PREFIX:
                return self._get_exports_access_rights(user_id=user_id, sub_path=sub_path)

            # otherwise assert 'root_folder' string corresponds to a valid UUID
            access_rights = await self.get_project_access_rights(user_id=user_id, project_id=ProjectID(root_folder))
            if not access_rights:
                _logger.warning(
                    "File %s references a project that does not exists in db",
                    file_id,
                )
                return AccessRights.none()

            return access_rights

        except (ValueError, AttributeError) as err:
            raise InvalidFileIdentifierError(
                identifier=file_id,
                details=str(err),
            ) from err

    async def get_file_access_rights(
        self,
        *,
        connection: AsyncConnection | None = None,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> AccessRights:
        """
        Returns access-rights of user (user_id) over data file resource (file_id)

        Raises InvalidFileIdentifierError
        """
        access_rights = await self._get_access_from_metadata_entry(
            connection=connection, user_id=user_id, file_id=file_id
        )

        if access_rights is not None:
            return access_rights

        return await self._get_access_without_metadata_entry(connection=connection, user_id=user_id, file_id=file_id)

    async def get_readable_project_ids(
        self,
        *,
        connection: AsyncConnection | None = None,
        user_id: UserID,
        product_name: ProductName,
    ) -> list[ProjectID]:
        """Returns a list of projects where user has granted read-access"""
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            return await _list_user_projects_access_rights_with_read_access(
                conn,
                user_id,
                product_name,
            )
