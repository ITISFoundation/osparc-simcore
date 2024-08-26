""" Database API

    - Adds a layer to the postgres API with a focus on the projects data
    - Shall be used as entry point for all the queries to the database regarding projects

"""

import logging
from contextlib import AsyncExitStack
from typing import Any, cast
from uuid import uuid1

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects import ProjectID, ProjectIDStr
from models_library.projects_comments import CommentID, ProjectsCommentsDB
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.resource_tracker import (
    PricingPlanAndUnitIdsTuple,
    PricingPlanId,
    PricingUnitId,
)
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletDB, WalletID
from pydantic import parse_obj_as
from pydantic.types import PositiveInt
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.logging_utils import get_log_record_extra, log_context
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.models.folders import folders_to_projects
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.models.wallets import wallets
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesRepo,
)
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
    ProjectNodesRepo,
)
from simcore_postgres_database.webserver_models import ProjectType, projects, users
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import and_
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type

from ..application_settings import ApplicationSettings
from ..db.models import projects_to_wallet, study_tags
from ..utils import now_str
from ._comments_db import (
    create_project_comment,
    delete_project_comment,
    get_project_comment,
    list_project_comments,
    total_project_comments,
    update_project_comment,
)
from ._db_utils import (
    ANY_USER_ID_SENTINEL,
    BaseProjectDB,
    PermissionStr,
    ProjectAccessRights,
    assemble_array_groups,
    check_project_permissions,
    convert_to_db_names,
    convert_to_schema_names,
    create_project_access_rights,
    patch_workbench,
    update_workbench,
)
from .exceptions import (
    ProjectDeleteError,
    ProjectInvalidRightsError,
    ProjectNodeResourcesInsufficientRightsError,
    ProjectNotFoundError,
)
from .models import ProjectDB, ProjectDict, UserProjectAccessRights

_logger = logging.getLogger(__name__)

APP_PROJECT_DBAPI = __name__ + ".ProjectDBAPI"
ANY_USER = ANY_USER_ID_SENTINEL

# pylint: disable=too-many-public-methods
# NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/3516


class ProjectDBAPI(BaseProjectDB):
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._engine = cast(Engine, app.get(APP_DB_ENGINE_KEY))

    def _init_engine(self) -> None:
        # Delays creation of engine because it setup_db does it on_startup
        self._engine = cast(Engine, self._app.get(APP_DB_ENGINE_KEY))
        if self._engine is None:
            msg = "Database subsystem was not initialized"
            raise ValueError(msg)

    @classmethod
    def get_from_app_context(cls, app: web.Application) -> "ProjectDBAPI":
        db: "ProjectDBAPI" = app[APP_PROJECT_DBAPI]
        return db

    @classmethod
    def set_once_in_app_context(cls, app: web.Application) -> "ProjectDBAPI":
        if app.get(APP_PROJECT_DBAPI) is None:
            app[APP_PROJECT_DBAPI] = ProjectDBAPI(app)
        db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
        return db

    @property
    def engine(self) -> Engine:
        # lazy evaluation
        if self._engine is None:
            self._init_engine()
        assert self._engine  # nosec
        return self._engine

    async def _insert_project_in_db(
        self,
        insert_values: ProjectDict,
        *,
        force_project_uuid: bool,
        product_name: str,
        project_tag_ids: list[int],
        project_nodes: dict[NodeID, ProjectNodeCreate] | None,
    ) -> ProjectDict:
        # Atomic transaction to insert project and update relations
        #  - Retries insert if UUID collision
        def _reraise_if_not_unique_uuid_error(err: UniqueViolation):
            if err.diag.constraint_name != "projects_uuid_key" or force_project_uuid:
                raise err

        selected_values: ProjectDict = {}
        async with self.engine.acquire() as conn:
            async for attempt in AsyncRetrying(retry=retry_if_exception_type(TryAgain)):
                with attempt:
                    async with conn.begin():
                        project_index = None
                        project_uuid = ProjectID(f"{insert_values['uuid']}")

                        try:
                            result: ResultProxy = await conn.execute(
                                projects.insert()
                                .values(**insert_values)
                                .returning(
                                    *[
                                        c
                                        for c in projects.columns
                                        if c.name not in ["type", "hidden", "published"]
                                    ]
                                )
                            )
                            row: RowProxy | None = await result.fetchone()
                            assert row  # nosec

                            selected_values = ProjectDict(row.items())
                            project_index = selected_values.pop("id")

                        except UniqueViolation as err:
                            _reraise_if_not_unique_uuid_error(err)

                            # Tries new uuid
                            insert_values["uuid"] = f"{uuid1()}"

                            # NOTE: Retry is over transaction context
                            # to rollout when a new insert is required
                            raise TryAgain from err

                        # Associate product to project: projects_to_product
                        await self.upsert_project_linked_product(
                            project_uuid=project_uuid,
                            product_name=product_name,
                            conn=conn,
                        )

                        # Associate tags to project: study_tags
                        assert project_index is not None  # nosec
                        await self._upsert_tags_in_project(
                            conn=conn,
                            project_index_id=project_index,
                            project_tags=project_tag_ids,
                        )
                        selected_values["tags"] = project_tag_ids

                        # NOTE: this will at some point completely replace workbench in the DB
                        if selected_values["workbench"]:
                            project_nodes_repo = ProjectNodesRepo(
                                project_uuid=project_uuid
                            )
                            if project_nodes is None:
                                project_nodes = {
                                    NodeID(node_id): ProjectNodeCreate(
                                        node_id=NodeID(node_id), required_resources={}
                                    )
                                    for node_id in selected_values["workbench"]
                                }

                            nodes = [
                                project_nodes.get(
                                    NodeID(node_id),
                                    ProjectNodeCreate(
                                        node_id=NodeID(node_id), required_resources={}
                                    ),
                                )
                                for node_id in selected_values["workbench"]
                            ]
                            await project_nodes_repo.add(conn, nodes=nodes)
        return selected_values

    async def insert_project(
        self,
        project: dict[str, Any],
        user_id: int | None,
        *,
        product_name: str,
        force_project_uuid: bool = False,
        force_as_template: bool = False,
        hidden: bool = False,
        project_nodes: dict[NodeID, ProjectNodeCreate] | None,
    ) -> dict[str, Any]:
        """Inserts a new project in the database

        - A valid uuid is automaticaly assigned to the project except if force_project_uuid=False. In the latter case,
        - passing project_nodes=None will auto-generate default ProjectNodeCreate, default resources will then be used.
        invalid uuid will raise an exception.

        :raises ProjectInvalidRightsError: assigning project to an unregistered user
        :raises ValidationError
        :return: inserted project
        """

        # NOTE: tags are removed in convert_to_db_names so we keep it
        project_tag_ids = parse_obj_as(list[int], project.get("tags", []).copy())
        insert_values = convert_to_db_names(project)
        insert_values.update(
            {
                "type": (
                    ProjectType.TEMPLATE.value
                    if (force_as_template or user_id is None)
                    else ProjectType.STANDARD.value
                ),
                "prj_owner": user_id if user_id else None,
                "hidden": hidden,
                # NOTE: this is very bad and leads to very weird conversions.
                # needs to be refactored!!! use arrow (https://github.com/ITISFoundation/osparc-simcore/issues/3797)
                "creation_date": now_str(),
                "last_change_date": now_str(),
            }
        )

        # validate access_rights. are the gids valid? also ensure prj_owner is in there
        if user_id:
            async with self.engine.acquire() as conn:
                primary_gid = await self._get_user_primary_group_gid(
                    conn, user_id=user_id
                )
            insert_values.setdefault("access_rights", {})
            insert_values["access_rights"].update(
                create_project_access_rights(primary_gid, ProjectAccessRights.OWNER)
            )

        # ensure we have the minimal amount of data here
        # All non-default in projects table
        insert_values.setdefault("name", "New Study")
        insert_values.setdefault("workbench", {})

        # must be valid uuid
        try:
            ProjectID(str(insert_values.get("uuid")))
        except ValueError:
            if force_project_uuid:
                raise
            insert_values["uuid"] = f"{uuid1()}"

        inserted_project = await self._insert_project_in_db(
            insert_values,
            force_project_uuid=force_project_uuid,
            product_name=product_name,
            project_tag_ids=project_tag_ids,
            project_nodes=project_nodes,
        )

        async with self.engine.acquire() as conn:
            # Returns created project with names as in the project schema
            user_email = await self._get_user_email(conn, user_id)

        # Convert to dict parsable by ProjectGet model
        return convert_to_schema_names(inserted_project, user_email)

    async def upsert_project_linked_product(
        self,
        project_uuid: ProjectID,
        product_name: str,
        conn: SAConnection | None = None,
    ) -> None:
        async with AsyncExitStack() as stack:
            if not conn:
                conn = await stack.enter_async_context(self.engine.acquire())
                assert conn  # nosec
            await conn.execute(
                pg_insert(projects_to_products)
                .values(project_uuid=f"{project_uuid}", product_name=product_name)
                .on_conflict_do_nothing()
            )

    async def list_projects(  # pylint: disable=too-many-arguments
        self,
        user_id: PositiveInt,
        *,
        product_name: str,
        settings: ApplicationSettings,
        filter_by_project_type: ProjectType | None = None,
        filter_by_services: list[dict] | None = None,
        only_published: bool | None = False,
        include_hidden: bool | None = False,
        offset: int | None = 0,
        limit: int | None = None,
        search: str | None = None,
        order_by: OrderBy = OrderBy(
            field=IDStr("last_change_date"), direction=OrderDirection.DESC
        ),
        folder_id: FolderID | None = None,
    ) -> tuple[list[dict[str, Any]], list[ProjectType], int]:
        assert (
            order_by.field in projects.columns
        ), "Guaranteed by ProjectListWithJsonStrParams"  # nosec

        async with self.engine.acquire() as conn:
            user_groups: list[RowProxy] = await self._list_user_groups(conn, user_id)

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
                    ).label("access_rights"),
                ).group_by(project_to_groups.c.project_uuid)
            ).subquery("access_rights_subquery")

            _join_query = projects.join(projects_to_products, isouter=True).join(
                access_rights_subquery, isouter=True
            )
            if settings.WEBSERVER_FOLDERS:
                _join_query = _join_query.join(folders_to_projects, isouter=True)

            query = (
                sa.select(
                    *[col for col in projects.columns if col.name != "access_rights"],
                    access_rights_subquery.c.access_rights,
                    projects_to_products.c.product_name,
                )
                .select_from(_join_query)
                .where(
                    (
                        (projects.c.type == filter_by_project_type.value)
                        if filter_by_project_type
                        else (projects.c.type.is_not(None))
                    )
                    & (
                        (projects.c.published.is_(True))
                        if only_published
                        else sa.text("")
                    )
                    & (
                        (projects.c.hidden.is_(False))
                        if not include_hidden
                        else sa.text("")
                    )
                    & (
                        (projects.c.prj_owner == user_id)
                        | sa.text(
                            f"jsonb_exists_any(access_rights_subquery.access_rights, {assemble_array_groups(user_groups)})"
                        )
                    )
                    & (
                        (projects_to_products.c.product_name == product_name)
                        # This was added for backward compatibility, including old projects not in the projects_to_products table.
                        | (projects_to_products.c.product_name.is_(None))
                    )
                )
            )
            if settings.WEBSERVER_FOLDERS:
                query = query.where(
                    folders_to_projects.c.folder_id == f"{folder_id}"
                    if folder_id
                    else folders_to_projects.c.folder_id.is_(None)
                )

            if search:
                query = query.join(users, isouter=True)
                query = query.where(
                    (projects.c.name.ilike(f"%{search}%"))
                    | (projects.c.description.ilike(f"%{search}%"))
                    | (projects.c.uuid.ilike(f"%{search}%"))
                    | (users.c.name.ilike(f"%{search}%"))
                )

            if order_by.direction == OrderDirection.ASC:
                query = query.order_by(sa.asc(getattr(projects.c, order_by.field)))
            else:
                query = query.order_by(sa.desc(getattr(projects.c, order_by.field)))

            total_number_of_projects = await conn.scalar(
                query.with_only_columns(func.count()).order_by(None)
            )
            assert total_number_of_projects is not None  # nosec

            prjs, prj_types = await self._execute_with_permission_check(
                conn,
                select_projects_query=query.offset(offset).limit(limit),
                user_id=user_id,
                user_groups=user_groups,
                filter_by_services=filter_by_services,
            )

            return (
                prjs,
                prj_types,
                total_number_of_projects,
            )

    async def list_projects_uuids(self, user_id: int) -> list[str]:
        async with self.engine.acquire() as conn:
            return [
                row[projects.c.uuid]
                async for row in conn.execute(
                    sa.select(projects.c.uuid).where(projects.c.prj_owner == user_id)
                )
            ]

    async def get_project(
        self,
        user_id: UserID,
        project_uuid: str,
        *,
        only_published: bool = False,
        only_templates: bool = False,
        check_permissions: PermissionStr = "read",
    ) -> tuple[ProjectDict, ProjectType]:
        """Returns all projects *owned* by the user

            - prj_owner
            - Notice that a user can have access to a template but he might not own it
            - Notice that a user can have access to a project where he/she has read access

        :raises ProjectNotFoundError: project is not assigned to user
        raises ProjectInvalidRightsError: if user has no access rights to do check_permissions
        """
        async with self.engine.acquire() as conn:
            project = await self._get_project(
                conn,
                user_id,
                project_uuid,
                only_published=only_published,
                only_templates=only_templates,
                check_permissions=check_permissions,
            )
            # pylint: disable=no-value-for-parameter
            user_email = await self._get_user_email(conn, project["prj_owner"])
            project_type = ProjectType(project[projects.c.type.name])
            return (
                convert_to_schema_names(project, user_email),
                project_type,
            )

    # NOTE: MD: I intentionally didn't include the workbench. There is a special interface
    # for the workbench, and at some point, this column should be removed from the table.
    # The same holds true for access_rights/ui/classifiers/quality, but we have decided to proceed step by step.
    _SELECTION_PROJECT_DB_ARGS = [  # noqa: RUF012
        projects.c.id,
        projects.c.type,
        projects.c.uuid,
        projects.c.name,
        projects.c.description,
        projects.c.thumbnail,
        projects.c.prj_owner,
        projects.c.creation_date,
        projects.c.last_change_date,
        projects.c.access_rights,
        projects.c.ui,
        projects.c.classifiers,
        projects.c.dev,
        projects.c.quality,
        projects.c.published,
        projects.c.hidden,
    ]

    async def get_project_db(self, project_uuid: ProjectID) -> ProjectDB:
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                sa.select(*self._SELECTION_PROJECT_DB_ARGS).where(
                    projects.c.uuid == f"{project_uuid}"
                )
            )
            row = await result.fetchone()
            if row is None:
                raise ProjectNotFoundError(project_uuid=project_uuid)
            return ProjectDB.from_orm(row)

    async def get_project_access_rights_for_user(
        self, user_id: UserID, project_uuid: ProjectID
    ) -> UserProjectAccessRights:
        """
        User project access rights. Aggregated across all his groups.
        """
        _SELECTION_ARGS = (
            user_to_groups.c.uid,
            func.max(project_to_groups.c.read.cast(INTEGER))
            .cast(BOOLEAN)
            .label("read"),
            func.max(project_to_groups.c.write.cast(INTEGER))
            .cast(BOOLEAN)
            .label("write"),
            func.max(project_to_groups.c.delete.cast(INTEGER))
            .cast(BOOLEAN)
            .label("delete"),
        )

        _JOIN_TABLES = user_to_groups.join(
            project_to_groups, user_to_groups.c.gid == project_to_groups.c.gid
        )

        stmt = (
            sa.select(*_SELECTION_ARGS)
            .select_from(_JOIN_TABLES)
            .where(
                (user_to_groups.c.uid == user_id)
                & (project_to_groups.c.project_uuid == f"{project_uuid}")
                & (project_to_groups.c.read == "true")
            )
            .group_by(user_to_groups.c.uid)
        )

        async with self.engine.acquire() as conn:
            result = await conn.execute(stmt)
            row = await result.fetchone()
            if row is None:
                raise ProjectInvalidRightsError(
                    user_id=user_id, project_uuid=project_uuid
                )
            return UserProjectAccessRights.from_orm(row)

    async def replace_project(
        self,
        new_project_data: ProjectDict,
        user_id: UserID,
        *,
        product_name: str,
        project_uuid: str,
    ) -> ProjectDict:
        """
        replaces a project from a user
        this method completely replaces a user project with new_project_data only keeping
        the old entries from the project workbench if they exists in the new project workbench.
        NOTE: This method does not allow to add or remove nodes. use add_project_node
        or remove_project_node to achieve this.

        Raises:
          ProjectInvalidRightsError
          ProjectInvalidUsageError in case nodes are added/removed, use add_project_node/remove_project_node
        """

        async with AsyncExitStack() as stack:
            stack.enter_context(
                log_context(
                    _logger,
                    logging.DEBUG,
                    msg=f"Replace {project_uuid=} for {user_id=}",
                    extra=get_log_record_extra(user_id=user_id),
                )
            )
            db_connection = await stack.enter_async_context(self.engine.acquire())
            await stack.enter_async_context(db_connection.begin())

            current_project: dict = await self._get_project(
                db_connection,
                user_id,
                project_uuid,
                exclude_foreign=["tags"],
                for_update=True,
            )
            user_groups = await self._list_user_groups(db_connection, user_id)
            check_project_permissions(current_project, user_id, user_groups, "write")
            # uuid can ONLY be set upon creation
            if current_project["uuid"] != new_project_data["uuid"]:
                raise ProjectInvalidRightsError(
                    user_id=user_id, project_uuid=new_project_data["uuid"]
                )
            # ensure the prj owner is always in the access rights
            owner_primary_gid = await self._get_user_primary_group_gid(
                db_connection, current_project[projects.c.prj_owner.key]
            )
            new_project_data.setdefault("accessRights", {}).update(
                create_project_access_rights(
                    owner_primary_gid, ProjectAccessRights.OWNER
                )
            )
            new_project_data = update_workbench(current_project, new_project_data)
            # update timestamps
            new_project_data["lastChangeDate"] = now_str()

            # now update it
            result = await db_connection.execute(
                # pylint: disable=no-value-for-parameter
                projects.update()
                .values(**convert_to_db_names(new_project_data))
                .where(projects.c.id == current_project[projects.c.id.key])
                .returning(literal_column("*"))
            )
            project = await result.fetchone()
            assert project  # nosec
            await self.upsert_project_linked_product(
                ProjectID(project_uuid), product_name, conn=db_connection
            )

            user_email = await self._get_user_email(db_connection, project.prj_owner)

            tags = await self._get_tags_by_project(
                db_connection, project_id=project[projects.c.id]
            )
            return convert_to_schema_names(project, user_email, tags=tags)
        msg = "linter unhappy without this"
        raise RuntimeError(msg)

    async def patch_project(
        self, project_uuid: ProjectID, new_partial_project_data: dict
    ) -> ProjectDB:
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                projects.update()
                .values(last_change_date=sa.func.now(), **new_partial_project_data)
                .where(projects.c.uuid == f"{project_uuid}")
                .returning(*self._SELECTION_PROJECT_DB_ARGS)
            )
            row = await result.fetchone()
            if row is None:
                raise ProjectNotFoundError(project_uuid=project_uuid)
            return ProjectDB.from_orm(row)

    async def update_project_owner_without_checking_permissions(
        self,
        project_uuid: ProjectIDStr,
        *,
        new_project_owner: UserID,
        new_project_access_rights: dict,
    ) -> None:
        """The garbage collector needs to alter the row without passing through the
        permissions layer (sic)."""
        async with self.engine.acquire() as conn:
            # now update it
            result: ResultProxy = await conn.execute(
                projects.update()
                .values(
                    prj_owner=new_project_owner,
                    access_rights=new_project_access_rights,
                    last_change_date=now_str(),
                )
                .where(projects.c.uuid == project_uuid)
            )
            result_row_count: int = result.rowcount
            assert result_row_count == 1  # nosec

    async def update_project_last_change_timestamp(self, project_uuid: ProjectIDStr):
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                # pylint: disable=no-value-for-parameter
                projects.update()
                .values(last_change_date=now_str())
                .where(projects.c.uuid == f"{project_uuid}")
            )
            if result.rowcount == 0:
                raise ProjectNotFoundError(project_uuid=project_uuid)

    async def delete_project(self, user_id: int, project_uuid: str):
        _logger.info(
            "Deleting project with %s for user with %s",
            f"{project_uuid=}",
            f"{user_id}",
        )

        async with self.engine.acquire() as conn, conn.begin():
            project = await self._get_project(
                conn, user_id, project_uuid, for_update=True
            )
            # if we have delete access we delete the project
            user_groups: list[RowProxy] = await self._list_user_groups(conn, user_id)
            check_project_permissions(project, user_id, user_groups, "delete")
            await conn.execute(
                # pylint: disable=no-value-for-parameter
                projects.delete().where(projects.c.uuid == project_uuid)
            )

    #
    # Project WORKBENCH / NODES
    #

    async def update_project_node_data(
        self,
        *,
        user_id: UserID,
        project_uuid: ProjectID,
        node_id: NodeID,
        product_name: str | None,
        new_node_data: dict[str, Any],
    ) -> tuple[ProjectDict, dict[NodeIDStr, Any]]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"update {project_uuid=}:{node_id=} for {user_id=}",
            extra=get_log_record_extra(user_id=user_id),
        ):
            partial_workbench_data: dict[NodeIDStr, Any] = {
                NodeIDStr(f"{node_id}"): new_node_data,
            }
            return await self._update_project_workbench(
                partial_workbench_data,
                user_id=user_id,
                project_uuid=f"{project_uuid}",
                product_name=product_name,
                allow_workbench_changes=False,
            )

    async def update_project_multiple_node_data(
        self,
        *,
        user_id: UserID,
        project_uuid: ProjectID,
        product_name: str | None,
        partial_workbench_data: dict[NodeIDStr, dict[str, Any]],
    ) -> tuple[ProjectDict, dict[NodeIDStr, Any]]:
        """
        Raises:
            ProjectInvalidUsageError if client tries to remove nodes using this method (use remove_project_node)
        """
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"update multiple nodes on {project_uuid=} for {user_id=}",
            extra=get_log_record_extra(user_id=user_id),
        ):
            return await self._update_project_workbench(
                partial_workbench_data,
                user_id=user_id,
                project_uuid=f"{project_uuid}",
                product_name=product_name,
                allow_workbench_changes=False,
            )

    async def _update_project_workbench(
        self,
        partial_workbench_data: dict[NodeIDStr, Any],
        *,
        user_id: int,
        project_uuid: str,
        product_name: str | None = None,
        allow_workbench_changes: bool,
    ) -> tuple[ProjectDict, dict[NodeIDStr, Any]]:
        """patches an EXISTING project workbench from a user
        new_project_data only contains the entries to modify

        - Example: to add a node: ```{new_node_id: {"key": node_key, "version": node_version, "label": node_label, ...}}```
        - Example: to modify a node ```{new_node_id: {"outputs": {"output_1": 2}}}```
        - Example: to remove a node ```{node_id: None}```

        raises NodeNotFoundError, ProjectInvalidRightsError, ProjectInvalidUsageError if allow_workbench_changes=False and nodes are added/removed

        """
        async with AsyncExitStack() as stack:
            stack.enter_context(
                log_context(
                    _logger,
                    logging.DEBUG,
                    msg=f"Patching workbench of {project_uuid=} for {user_id=}",
                    extra=get_log_record_extra(user_id=user_id),
                )
            )
            db_connection = await stack.enter_async_context(self.engine.acquire())
            await stack.enter_async_context(db_connection.begin())

            current_project: dict = await self._get_project(
                db_connection,
                user_id,
                project_uuid,
                exclude_foreign=["tags"],
                for_update=True,
            )
            user_groups: list[RowProxy] = await self._list_user_groups(
                db_connection, user_id
            )
            check_project_permissions(current_project, user_id, user_groups, "write")

            new_project_data, changed_entries = patch_workbench(
                current_project,
                new_partial_workbench_data=partial_workbench_data,
                allow_workbench_changes=allow_workbench_changes,
            )

            # update timestamps
            new_project_data["lastChangeDate"] = now_str()

            result = await db_connection.execute(
                projects.update()
                .values(**convert_to_db_names(new_project_data))
                .where(projects.c.id == current_project[projects.c.id.key])
                .returning(literal_column("*"))
            )
            project = await result.fetchone()
            assert project  # nosec
            if product_name:
                await self.upsert_project_linked_product(
                    ProjectID(project_uuid), product_name, conn=db_connection
                )
            user_email = await self._get_user_email(db_connection, project.prj_owner)

            tags = await self._get_tags_by_project(
                db_connection, project_id=project[projects.c.id]
            )
            return (
                convert_to_schema_names(project, user_email, tags=tags),
                changed_entries,
            )
        msg = "linter unhappy without this"
        raise RuntimeError(msg)

    async def add_project_node(
        self,
        user_id: UserID,
        project_id: ProjectID,
        node: ProjectNodeCreate,
        old_struct_node: Node,
        product_name: str,
    ) -> None:
        # NOTE: permission check is done currently in update_project_workbench!
        partial_workbench_data: dict[NodeIDStr, Any] = {
            NodeIDStr(f"{node.node_id}"): jsonable_encoder(
                old_struct_node,
                exclude_unset=True,
            ),
        }
        await self._update_project_workbench(
            partial_workbench_data,
            user_id=user_id,
            project_uuid=f"{project_id}",
            product_name=product_name,
            allow_workbench_changes=True,
        )
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        async with self.engine.acquire() as conn:
            await project_nodes_repo.add(conn, nodes=[node])

    async def remove_project_node(
        self, user_id: UserID, project_id: ProjectID, node_id: NodeID
    ) -> None:
        # NOTE: permission check is done currently in update_project_workbench!
        partial_workbench_data: dict[NodeIDStr, Any] = {
            NodeIDStr(f"{node_id}"): None,
        }
        await self._update_project_workbench(
            partial_workbench_data,
            user_id=user_id,
            project_uuid=f"{project_id}",
            allow_workbench_changes=True,
        )
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        async with self.engine.acquire() as conn:
            await project_nodes_repo.delete(conn, node_id=node_id)

    async def get_project_node(  # NOTE: Not all Node data are here yet; they are in the workbench of a Project, waiting to be moved here.
        self, project_id: ProjectID, node_id: NodeID
    ) -> ProjectNode:
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        async with self.engine.acquire() as conn:
            return await project_nodes_repo.get(conn, node_id=node_id)

    async def update_project_node(
        self,
        user_id: UserID,
        project_id: ProjectID,
        node_id: NodeID,
        product_name: str,
        *,
        check_update_allowed: bool,
        **values,
    ) -> ProjectNode:
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        async with self.engine.acquire() as conn:
            if check_update_allowed:
                user_extra_properties = (
                    await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                        conn, user_id=user_id, product_name=product_name
                    )
                )
                if not user_extra_properties.override_services_specifications:
                    msg = (
                        "User not allowed to modify node resources! "
                        "TIP: Ask your administrator or contact support"
                    )
                    raise ProjectNodeResourcesInsufficientRightsError(msg)
            return await project_nodes_repo.update(conn, node_id=node_id, **values)

    async def list_project_nodes(self, project_id: ProjectID) -> list[ProjectNode]:
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        async with self.engine.acquire() as conn:
            return await project_nodes_repo.list(conn)

    async def node_id_exists(self, node_id: NodeID) -> bool:
        """Returns True if the node id exists in any of the available projects"""
        async with self.engine.acquire() as conn:
            num_entries = await conn.scalar(
                sa.select(func.count())
                .select_from(projects_nodes)
                .where(projects_nodes.c.node_id == f"{node_id}")
            )
        assert num_entries is not None  # nosec
        assert isinstance(num_entries, int)  # nosec
        return bool(num_entries > 0)

    async def list_node_ids_in_project(self, project_uuid: ProjectID) -> set[NodeID]:
        """Returns a set containing all the node_ids from project with project_uuid"""
        repo = ProjectNodesRepo(project_uuid=project_uuid)
        async with self.engine.acquire() as conn:
            list_of_nodes = await repo.list(conn)
        return {node.node_id for node in list_of_nodes}

    #
    # Project NODES to Pricing Units
    #

    async def get_project_node_pricing_unit_id(
        self,
        project_uuid: ProjectID,
        node_uuid: NodeID,
    ) -> PricingPlanAndUnitIdsTuple | None:
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_uuid)
        async with self.engine.acquire() as conn:
            output = await project_nodes_repo.get_project_node_pricing_unit_id(
                conn, node_uuid=node_uuid
            )
            if output:
                pricing_plan_id, pricing_unit_id = output
                return PricingPlanAndUnitIdsTuple(pricing_plan_id, pricing_unit_id)
            return None

    async def connect_pricing_unit_to_project_node(
        self,
        project_uuid: ProjectID,
        node_uuid: NodeID,
        pricing_plan_id: PricingPlanId,
        pricing_unit_id: PricingUnitId,
    ) -> None:
        async with self.engine.acquire() as conn:
            project_nodes_repo = ProjectNodesRepo(project_uuid=project_uuid)
            await project_nodes_repo.connect_pricing_unit_to_project_node(
                conn,
                node_uuid=node_uuid,
                pricing_plan_id=pricing_plan_id,
                pricing_unit_id=pricing_unit_id,
            )

    #
    # Project ACCESS RIGHTS/PERMISSIONS
    #

    async def has_permission(
        self, user_id: UserID, project_uuid: str, permission: PermissionStr
    ) -> bool:
        """
        NOTE: this function should never raise
        NOTE: if user_id does not exist it is not an issue
        """

        async with self.engine.acquire() as conn:
            try:
                project = await self._get_project(conn, user_id, project_uuid)
                user_groups: list[RowProxy] = await self._list_user_groups(
                    conn, user_id
                )
                check_project_permissions(project, user_id, user_groups, permission)
                return True
            except (ProjectInvalidRightsError, ProjectNotFoundError):
                return False

    async def check_delete_project_permission(self, user_id: int, project_uuid: str):
        """
        raises ProjectInvalidRightsError
        """
        async with self.engine.acquire() as conn, conn.begin():
            project = await self._get_project(
                conn, user_id, project_uuid, for_update=True
            )
            # if we have delete access we delete the project
            user_groups: list[RowProxy] = await self._list_user_groups(conn, user_id)
            check_project_permissions(project, user_id, user_groups, "delete")

    #
    # Project TAGS
    #

    async def add_tag(
        self, user_id: int, project_uuid: str, tag_id: int
    ) -> ProjectDict:
        """Creates a tag and associates it to this project"""
        async with self.engine.acquire() as conn:
            project = await self._get_project(
                conn, user_id=user_id, project_uuid=project_uuid, exclude_foreign=None
            )
            user_email = await self._get_user_email(conn, user_id)

            project_tags: list[int] = project["tags"]

            # pylint: disable=no-value-for-parameter
            if tag_id not in project_tags:
                await conn.execute(
                    study_tags.insert().values(
                        study_id=project["id"],
                        tag_id=tag_id,
                    )
                )
                project_tags.append(tag_id)

            return convert_to_schema_names(project, user_email)

    async def remove_tag(
        self, user_id: int, project_uuid: str, tag_id: int
    ) -> ProjectDict:
        async with self.engine.acquire() as conn:
            project = await self._get_project(conn, user_id, project_uuid)
            user_email = await self._get_user_email(conn, user_id)
            # pylint: disable=no-value-for-parameter
            query = study_tags.delete().where(
                and_(
                    study_tags.c.study_id == project["id"],
                    study_tags.c.tag_id == tag_id,
                )
            )
            async with conn.execute(query):
                if tag_id in project["tags"]:
                    project["tags"].remove(tag_id)
                return convert_to_schema_names(project, user_email)

    #
    # Project Comments
    #

    async def create_project_comment(
        self, project_uuid: ProjectID, user_id: UserID, contents: str
    ) -> CommentID:
        async with self.engine.acquire() as conn:
            return await create_project_comment(conn, project_uuid, user_id, contents)

    async def list_project_comments(
        self,
        project_uuid: ProjectID,
        offset: PositiveInt,
        limit: int,
    ) -> list[ProjectsCommentsDB]:
        async with self.engine.acquire() as conn:
            return await list_project_comments(conn, project_uuid, offset, limit)

    async def total_project_comments(
        self,
        project_uuid: ProjectID,
    ) -> PositiveInt:
        async with self.engine.acquire() as conn:
            return await total_project_comments(conn, project_uuid)

    async def update_project_comment(
        self,
        comment_id: CommentID,
        project_uuid: ProjectID,
        contents: str,
    ) -> ProjectsCommentsDB:
        async with self.engine.acquire() as conn:
            return await update_project_comment(
                conn, comment_id, project_uuid, contents
            )

    async def delete_project_comment(self, comment_id: CommentID) -> None:
        async with self.engine.acquire() as conn:
            return await delete_project_comment(conn, comment_id)

    async def get_project_comment(self, comment_id: CommentID) -> ProjectsCommentsDB:
        async with self.engine.acquire() as conn:
            return await get_project_comment(conn, comment_id)

    #
    # Project Wallet
    #

    async def get_project_wallet(
        self,
        project_uuid: ProjectID,
    ) -> WalletDB | None:
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                sa.select(
                    wallets.c.wallet_id,
                    wallets.c.name,
                    wallets.c.description,
                    wallets.c.owner,
                    wallets.c.thumbnail,
                    wallets.c.status,
                    wallets.c.created,
                    wallets.c.modified,
                )
                .select_from(
                    projects_to_wallet.join(
                        wallets, projects_to_wallet.c.wallet_id == wallets.c.wallet_id
                    )
                )
                .where(projects_to_wallet.c.project_uuid == f"{project_uuid}")
            )
            row = await result.fetchone()
            return parse_obj_as(WalletDB, row) if row else None

    async def connect_wallet_to_project(
        self,
        project_uuid: ProjectID,
        wallet_id: WalletID,
    ) -> None:
        async with self.engine.acquire() as conn:
            insert_stmt = pg_insert(projects_to_wallet).values(
                project_uuid=f"{project_uuid}",
                wallet_id=wallet_id,
                created=sa.func.now(),
                modified=sa.func.now(),
            )
            on_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[
                    projects_to_wallet.c.project_uuid,
                ],
                set_={
                    "wallet_id": insert_stmt.excluded.wallet_id,
                    "modified": sa.func.now(),
                },
            )
            await conn.execute(on_update_stmt)

    #
    # Project HIDDEN column
    #
    async def is_hidden(self, project_uuid: ProjectID) -> bool:
        async with self.engine.acquire() as conn:
            result = await conn.scalar(
                sa.select(projects.c.hidden).where(projects.c.uuid == f"{project_uuid}")
            )
        return bool(result)

    async def set_hidden_flag(self, project_uuid: ProjectID, *, hidden: bool):
        async with self.engine.acquire() as conn:
            stmt = (
                projects.update()
                .values(hidden=hidden)
                .where(projects.c.uuid == f"{project_uuid}")
            )
            await conn.execute(stmt)

    #
    # Project TYPE column
    #

    async def get_project_type(self, project_uuid: ProjectID) -> ProjectType:
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                sa.select(projects.c.type).where(projects.c.uuid == f"{project_uuid}")
            )
            row = await result.first()
            if row:
                return ProjectType(row[projects.c.type])
        raise ProjectNotFoundError(project_uuid=project_uuid)

    #
    # MISC
    #

    async def check_project_has_only_one_product(self, project_uuid: ProjectID) -> None:
        async with self.engine.acquire() as conn:
            num_products_linked_to_project = await conn.scalar(
                sa.select(func.count())
                .select_from(projects_to_products)
                .where(projects_to_products.c.project_uuid == f"{project_uuid}")
            )
            assert isinstance(num_products_linked_to_project, int)  # nosec
        if num_products_linked_to_project > 1:
            # NOTE:
            # in agreement with @odeimaiz :
            #
            # we decided that this precise use-case where we have a project in 2 products at the same time does not exist now and its chances to ever come is small -> therefore we do not treat it for now
            # nevertheless in case it would be done this way (which would by the way need a manual intervention already to set it up), at least it would not be possible to delete the project in one product to prevent some unwanted deletion.
            # reduce time to develop by not implementing something that might never be necessary
            raise ProjectDeleteError(
                project_uuid=project_uuid,
                reason="Project has more than one linked product. This needs manual intervention. Please contact oSparc support.",
            )


def setup_projects_db(app: web.Application):
    # NOTE: inits once per app
    return ProjectDBAPI.set_once_in_app_context(app)


__all__ = ("ProjectAccessRights",)
