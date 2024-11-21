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
from models_library.folders import FolderQuery, FolderScope
from models_library.products import ProductName
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
from models_library.workspaces import WorkspaceQuery, WorkspaceScope
from pydantic import TypeAdapter
from pydantic.types import PositiveInt
from servicelib.aiohttp.application_keys import APP_AIOPG_ENGINE_KEY
from servicelib.logging_utils import get_log_record_extra, log_context
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.models.projects_tags import projects_tags
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.models.wallets import wallets
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
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
from sqlalchemy.sql import ColumnElement, CompoundSelect, Select, and_
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type

from ..db.models import projects_tags, projects_to_wallet
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
    ProjectAccessRights,
    assemble_array_groups,
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
from .models import (
    ProjectDB,
    ProjectDict,
    UserProjectAccessRightsDB,
    UserSpecificProjectDataDB,
)

_logger = logging.getLogger(__name__)

APP_PROJECT_DBAPI = __name__ + ".ProjectDBAPI"
ANY_USER = ANY_USER_ID_SENTINEL

# pylint: disable=too-many-public-methods
# NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/3516


class ProjectDBAPI(BaseProjectDB):
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._engine = cast(Engine, app.get(APP_AIOPG_ENGINE_KEY))

    def _init_engine(self) -> None:
        # Delays creation of engine because it setup_db does it on_startup
        self._engine = cast(Engine, self._app.get(APP_AIOPG_ENGINE_KEY))
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
                            project_uuid=project_uuid,
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
        project_tag_ids = TypeAdapter(list[int]).validate_python(
            project.get("tags", []).copy()
        )
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

        insert_values.setdefault("workspace_id", None)

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
            .filter(
                project_to_groups.c.read  # Filters out entries where "read" is False
            )
            .label("access_rights"),
        ).group_by(project_to_groups.c.project_uuid)
    ).subquery("access_rights_subquery")

    async def list_projects(  # pylint: disable=too-many-arguments,too-many-statements,too-many-branches
        self,
        *,
        product_name: ProductName,
        user_id: PositiveInt,
        # hierarchy filters
        workspace_query: WorkspaceQuery,
        folder_query: FolderQuery,
        # attribute filters
        filter_by_project_type: ProjectType | None = None,
        filter_by_services: list[dict] | None = None,
        filter_published: bool | None = False,
        filter_hidden: bool | None = False,
        filter_trashed: bool | None = False,
        filter_by_text: str | None = None,
        filter_tag_ids_list: list[int] | None = None,
        # pagination
        offset: int | None = 0,
        limit: int | None = None,
        # order
        order_by: OrderBy = OrderBy(
            field=IDStr("last_change_date"), direction=OrderDirection.DESC
        ),
    ) -> tuple[list[dict[str, Any]], list[ProjectType], int]:
        if filter_tag_ids_list is None:
            filter_tag_ids_list = []

        async with self.engine.acquire() as conn:
            user_groups: list[RowProxy] = await self._list_user_groups(conn, user_id)

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

            project_tags_subquery = (
                sa.select(
                    projects_tags.c.project_id,
                    sa.func.array_agg(projects_tags.c.tag_id).label("tags"),
                )
                .where(projects_tags.c.project_id.is_not(None))
                .group_by(projects_tags.c.project_id)
            ).subquery("project_tags_subquery")

            ###
            # Private workspace query
            ###

            if workspace_query.workspace_scope is not WorkspaceScope.SHARED:
                assert workspace_query.workspace_scope in (  # nosec
                    WorkspaceScope.PRIVATE,
                    WorkspaceScope.ALL,
                )

                private_workspace_query = (
                    sa.select(
                        *[
                            col
                            for col in projects.columns
                            if col.name not in ["access_rights"]
                        ],
                        self.access_rights_subquery.c.access_rights,
                        projects_to_products.c.product_name,
                        projects_to_folders.c.folder_id,
                        sa.func.coalesce(
                            project_tags_subquery.c.tags,
                            sa.cast(sa.text("'{}'"), sa.ARRAY(sa.Integer)),
                        ).label("tags"),
                    )
                    .select_from(
                        projects.join(self.access_rights_subquery, isouter=True)
                        .join(projects_to_products)
                        .join(
                            projects_to_folders,
                            (
                                (projects_to_folders.c.project_uuid == projects.c.uuid)
                                & (projects_to_folders.c.user_id == user_id)
                            ),
                            isouter=True,
                        )
                        .join(project_tags_subquery, isouter=True)
                    )
                    .where(
                        (
                            (projects.c.prj_owner == user_id)
                            | sa.text(
                                f"jsonb_exists_any(access_rights_subquery.access_rights, {assemble_array_groups(user_groups)})"
                            )
                        )
                        & (projects.c.workspace_id.is_(None))  # <-- Private workspace
                        & (projects_to_products.c.product_name == product_name)
                    )
                )
                if filter_by_text is not None:
                    private_workspace_query = private_workspace_query.join(
                        users, users.c.id == projects.c.prj_owner, isouter=True
                    )
            else:
                private_workspace_query = None

            ###
            # Shared workspace query
            ###

            if workspace_query.workspace_scope is not WorkspaceScope.PRIVATE:
                assert workspace_query.workspace_scope in (
                    WorkspaceScope.SHARED,
                    WorkspaceScope.ALL,
                )  # nosec

                shared_workspace_query = (
                    sa.select(
                        *[
                            col
                            for col in projects.columns
                            if col.name not in ["access_rights"]
                        ],
                        workspace_access_rights_subquery.c.access_rights,
                        projects_to_products.c.product_name,
                        projects_to_folders.c.folder_id,
                        sa.func.coalesce(
                            project_tags_subquery.c.tags,
                            sa.cast(sa.text("'{}'"), sa.ARRAY(sa.Integer)),
                        ).label("tags"),
                    )
                    .select_from(
                        projects.join(
                            workspace_access_rights_subquery,
                            projects.c.workspace_id
                            == workspace_access_rights_subquery.c.workspace_id,
                        )
                        .join(projects_to_products)
                        .join(
                            projects_to_folders,
                            (
                                (projects_to_folders.c.project_uuid == projects.c.uuid)
                                & (projects_to_folders.c.user_id.is_(None))
                            ),
                            isouter=True,
                        )
                        .join(project_tags_subquery, isouter=True)
                    )
                    .where(
                        (
                            sa.text(
                                f"jsonb_exists_any(workspace_access_rights_subquery.access_rights, {assemble_array_groups(user_groups)})"
                            )
                        )
                        & (projects_to_products.c.product_name == product_name)
                    )
                )
                if workspace_query.workspace_scope == WorkspaceScope.ALL:
                    shared_workspace_query = shared_workspace_query.where(
                        projects.c.workspace_id.is_not(
                            None
                        )  # <-- All shared workspaces
                    )
                if filter_by_text is not None:
                    shared_workspace_query = shared_workspace_query.join(
                        users, users.c.id == projects.c.prj_owner, isouter=True
                    )

                else:
                    assert (
                        workspace_query.workspace_scope == WorkspaceScope.SHARED
                    )  # nosec
                    shared_workspace_query = shared_workspace_query.where(
                        projects.c.workspace_id
                        == workspace_query.workspace_id  # <-- Specific shared workspace
                    )

            else:
                shared_workspace_query = None

            ###
            # Attributes Filters
            ###

            attributes_filters: list[ColumnElement] = []
            if filter_by_project_type is not None:
                attributes_filters.append(
                    projects.c.type == filter_by_project_type.value
                )

            if filter_hidden is not None:
                attributes_filters.append(projects.c.hidden.is_(filter_hidden))

            if filter_published is not None:
                attributes_filters.append(projects.c.published.is_(filter_published))

            if filter_trashed is not None:
                attributes_filters.append(
                    # marked explicitly as trashed
                    (
                        projects.c.trashed_at.is_not(None)
                        & projects.c.trashed_explicitly.is_(True)
                    )
                    if filter_trashed
                    # not marked as trashed
                    else projects.c.trashed_at.is_(None)
                )
            if filter_by_text is not None:
                attributes_filters.append(
                    (projects.c.name.ilike(f"%{filter_by_text}%"))
                    | (projects.c.description.ilike(f"%{filter_by_text}%"))
                    | (projects.c.uuid.ilike(f"%{filter_by_text}%"))
                    | (users.c.name.ilike(f"%{filter_by_text}%"))
                )
            if filter_tag_ids_list:
                attributes_filters.append(
                    sa.func.coalesce(
                        project_tags_subquery.c.tags,
                        sa.cast(sa.text("'{}'"), sa.ARRAY(sa.Integer)),
                    ).op("@>")(filter_tag_ids_list)
                )
            if folder_query.folder_scope is not FolderScope.ALL:
                if folder_query.folder_scope == FolderScope.SPECIFIC:
                    attributes_filters.append(
                        projects_to_folders.c.folder_id == folder_query.folder_id
                    )
                else:
                    assert folder_query.folder_scope == FolderScope.ROOT  # nosec
                    attributes_filters.append(projects_to_folders.c.folder_id.is_(None))

            ###
            # Combined
            ###

            combined_query: CompoundSelect | Select | None = None
            if (
                private_workspace_query is not None
                and shared_workspace_query is not None
            ):
                combined_query = sa.union_all(
                    private_workspace_query.where(sa.and_(*attributes_filters)),
                    shared_workspace_query.where(sa.and_(*attributes_filters)),
                )
            elif private_workspace_query is not None:
                combined_query = private_workspace_query.where(
                    sa.and_(*attributes_filters)
                )
            elif shared_workspace_query is not None:
                combined_query = shared_workspace_query.where(
                    sa.and_(*attributes_filters)
                )

            if combined_query is None:
                msg = f"No valid queries were provided to combine. Workspace scope: {workspace_query.workspace_scope}"
                raise ValueError(msg)
            count_query = sa.select(func.count()).select_from(combined_query.subquery())
            total_count = await conn.scalar(count_query)

            if order_by.direction == OrderDirection.ASC:
                combined_query = combined_query.order_by(
                    sa.asc(getattr(projects.c, order_by.field))
                )
            else:
                combined_query = combined_query.order_by(
                    sa.desc(getattr(projects.c, order_by.field))
                )

            prjs, prj_types = await self._execute_without_permission_check(
                conn,
                user_id=user_id,
                select_projects_query=combined_query.offset(offset).limit(limit),
                filter_by_services=filter_by_services,
            )

            return (
                prjs,
                prj_types,
                cast(int, total_count),
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
        project_uuid: str,
        *,
        only_published: bool = False,
        only_templates: bool = False,
    ) -> tuple[ProjectDict, ProjectType]:
        """
        This is a legacy function that retrieves the project resource along with additional adjustments.
        The `get_project_db` function is now recommended for use when interacting with the projects DB layer.
        """
        async with self.engine.acquire() as conn:
            project = await self._get_project(
                conn,
                project_uuid,
                only_published=only_published,
                only_templates=only_templates,
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
        projects.c.ui,
        projects.c.classifiers,
        projects.c.dev,
        projects.c.quality,
        projects.c.published,
        projects.c.hidden,
        projects.c.workspace_id,
        projects.c.trashed_at,
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
            return ProjectDB.model_validate(row)

    async def get_user_specific_project_data_db(
        self, project_uuid: ProjectID, private_workspace_user_id_or_none: UserID | None
    ) -> UserSpecificProjectDataDB:
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                sa.select(
                    *self._SELECTION_PROJECT_DB_ARGS, projects_to_folders.c.folder_id
                )
                .select_from(
                    projects.join(
                        projects_to_folders,
                        (
                            (projects_to_folders.c.project_uuid == projects.c.uuid)
                            & (
                                projects_to_folders.c.user_id
                                == private_workspace_user_id_or_none
                            )
                        ),
                        isouter=True,
                    )
                )
                .where(projects.c.uuid == f"{project_uuid}")
            )
            row = await result.fetchone()
            if row is None:
                raise ProjectNotFoundError(project_uuid=project_uuid)
            return UserSpecificProjectDataDB.model_validate(row)

    async def get_pure_project_access_rights_without_workspace(
        self, user_id: UserID, project_uuid: ProjectID
    ) -> UserProjectAccessRightsDB:
        """
        Be careful what you want. You should use `get_user_project_access_rights` to get access rights on the
        project. It depends on which context you are in, whether private or shared workspace.

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
            return UserProjectAccessRightsDB.model_validate(row)

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
                project_uuid,
                exclude_foreign=["tags"],
                for_update=True,
            )

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
            return ProjectDB.model_validate(row)

    async def get_project_product(self, project_uuid: ProjectID) -> ProductName:
        async with self.engine.acquire() as conn:
            result = await conn.execute(
                sa.select(projects_to_products.c.product_name)
                .join(projects)
                .where(projects.c.uuid == f"{project_uuid}")
            )
            row = await result.fetchone()
            if row is None:
                raise ProjectNotFoundError(project_uuid=project_uuid)
            return cast(str, row[0])

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
                project_uuid,
                exclude_foreign=["tags"],
                for_update=True,
            )

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
    # Project TAGS
    #

    async def add_tag(
        self, user_id: int, project_uuid: str, tag_id: int
    ) -> ProjectDict:
        """Creates a tag and associates it to this project"""
        async with self.engine.acquire() as conn:
            project = await self._get_project(
                conn, project_uuid=project_uuid, exclude_foreign=None
            )
            user_email = await self._get_user_email(conn, user_id)

            project_tags: list[int] = project["tags"]

            # pylint: disable=no-value-for-parameter
            if tag_id not in project_tags:
                await conn.execute(
                    projects_tags.insert().values(
                        project_id=project["id"],
                        tag_id=tag_id,
                        project_uuid_for_rut=project["uuid"],
                    )
                )
                project_tags.append(tag_id)

            return convert_to_schema_names(project, user_email)

    async def remove_tag(
        self, user_id: int, project_uuid: str, tag_id: int
    ) -> ProjectDict:
        async with self.engine.acquire() as conn:
            project = await self._get_project(conn, project_uuid)
            user_email = await self._get_user_email(conn, user_id)
            # pylint: disable=no-value-for-parameter
            query = projects_tags.delete().where(
                and_(
                    projects_tags.c.project_id == project["id"],
                    projects_tags.c.tag_id == tag_id,
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
            return WalletDB.model_validate(row) if row else None

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
