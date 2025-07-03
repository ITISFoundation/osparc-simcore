# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.products import ProductName
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.models.comp_pipeline import StateType, comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.models.services import services_access_rights
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodeCreate,
    ProjectNodesRepo,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from .helpers.postgres_tools import insert_and_get_row_lifespan


@pytest.fixture()
def create_registered_user(
    postgres_db: sa.engine.Engine, faker: Faker
) -> Iterator[Callable[..., dict]]:
    created_user_ids = []

    def creator(**user_kwargs) -> dict[str, Any]:
        with postgres_db.connect() as con:
            # removes all users before continuing
            user_config = {
                "id": len(created_user_ids) + 1,
                "name": faker.name(),
                "email": faker.email(),
                "password_hash": faker.password(),
                "status": UserStatus.ACTIVE,
                "role": UserRole.USER,
            }
            user_config.update(user_kwargs)

            con.execute(
                users.insert().values(user_config).returning(sa.literal_column("*"))
            )
            # this is needed to get the primary_gid correctly
            result = con.execute(
                sa.select(users).where(users.c.id == user_config["id"])
            )
            user = result.first()
            assert user
            print(f"--> created {user=}")
            created_user_ids.append(user["id"])
        return dict(user._asdict())

    yield creator

    with postgres_db.connect() as con:
        con.execute(users.delete().where(users.c.id.in_(created_user_ids)))
    print(f"<-- deleted users {created_user_ids=}")


@pytest.fixture
async def with_product(
    sqlalchemy_async_engine: AsyncEngine, product: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        sqlalchemy_async_engine,
        table=products,
        values=product,
        pk_col=products.c.name,
    ) as created_product:
        yield created_product


@pytest.fixture
async def project(
    sqlalchemy_async_engine: AsyncEngine, faker: Faker, product_name: ProductName
) -> AsyncIterator[Callable[..., Awaitable[ProjectAtDB]]]:
    created_project_ids: list[str] = []

    async def creator(
        user: dict[str, Any],
        *,
        project_nodes_overrides: dict[str, Any] | None = None,
        **project_overrides,
    ) -> ProjectAtDB:
        project_uuid = uuid4()
        print(f"Created new project with uuid={project_uuid}")
        project_config = {
            "uuid": f"{project_uuid}",
            "name": faker.name(),
            "type": ProjectType.STANDARD.name,
            "description": faker.text(),
            "prj_owner": user["id"],
            "access_rights": {"1": {"read": True, "write": True, "delete": True}},
            "thumbnail": "",
            "workbench": {},
        }
        project_config.update(**project_overrides)
        async with sqlalchemy_async_engine.connect() as con, con.begin():
            result = await con.execute(
                projects.insert()
                .values(**project_config)
                .returning(sa.literal_column("*"))
            )

            inserted_project = ProjectAtDB.model_validate(result.one())
            project_nodes_repo = ProjectNodesRepo(project_uuid=project_uuid)
            # NOTE: currently no resources is passed until it becomes necessary
            default_node_config = {
                "required_resources": {},
                "key": faker.pystr(),
                "version": faker.pystr(),
                "label": faker.pystr(),
            }
            if project_nodes_overrides:
                default_node_config.update(project_nodes_overrides)
            await project_nodes_repo.add(
                con,
                nodes=[
                    ProjectNodeCreate(node_id=NodeID(node_id), **default_node_config)
                    for node_id in inserted_project.workbench
                ],
            )
            await con.execute(
                projects_to_products.insert().values(
                    project_uuid=f"{inserted_project.uuid}",
                    product_name=product_name,
                )
            )
        print(f"--> created {inserted_project=}")
        created_project_ids.append(f"{inserted_project.uuid}")
        return inserted_project

    yield creator

    # cleanup
    async with sqlalchemy_async_engine.begin() as con:
        await con.execute(
            projects.delete().where(projects.c.uuid.in_(created_project_ids))
        )
    print(f"<-- delete projects {created_project_ids=}")


@pytest.fixture
async def create_pipeline(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    created_pipeline_ids: list[str] = []

    async def creator(**pipeline_kwargs) -> dict[str, Any]:
        pipeline_config = {
            "project_id": f"{uuid4()}",
            "dag_adjacency_list": {},
            "state": StateType.NOT_STARTED,
        }
        pipeline_config.update(**pipeline_kwargs)
        async with sqlalchemy_async_engine.begin() as conn:
            result = await conn.execute(
                comp_pipeline.insert()
                .values(**pipeline_config)
                .returning(sa.literal_column("*"))
            )
            row = result.one()
            new_pipeline = row._asdict()
            created_pipeline_ids.append(new_pipeline["project_id"])
            return new_pipeline

    yield creator

    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_pipeline.delete().where(
                comp_pipeline.c.project_id.in_(created_pipeline_ids)
            )
        )


@pytest.fixture
async def create_comp_task(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    created_task_ids: list[int] = []

    async def creator(project_id: ProjectID, **task_kwargs) -> dict[str, Any]:
        task_config = {"project_id": f"{project_id}"} | task_kwargs
        async with sqlalchemy_async_engine.begin() as conn:
            result = await conn.execute(
                comp_tasks.insert()
                .values(**task_config)
                .returning(sa.literal_column("*"))
            )
            row = result.one()
            new_task = row._asdict()
            created_task_ids.append(new_task["task_id"])
        return new_task

    yield creator

    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.delete().where(comp_tasks.c.task_id.in_(created_task_ids))
        )


@pytest.fixture
def grant_service_access_rights(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable[..., dict[str, Any]]]:
    """Fixture to grant access rights on a service for a given group.

    Creates a row in the services_access_rights table with the provided parameters and cleans up after the test.
    """
    created_entries: list[tuple[str, str, int, str]] = []

    def creator(
        *,
        service_key: str,
        service_version: str,
        group_id: int = 1,
        product_name: str = "osparc",
        execute_access: bool = True,
        write_access: bool = False,
    ) -> dict[str, Any]:
        values = {
            "key": service_key,
            "version": service_version,
            "gid": group_id,
            "product_name": product_name,
            "execute_access": execute_access,
            "write_access": write_access,
        }

        # Directly use SQLAlchemy to insert and retrieve the row
        with postgres_db.begin() as conn:
            # Insert the row
            conn.execute(services_access_rights.insert().values(**values))

            # Retrieve the inserted row
            result = conn.execute(
                sa.select(services_access_rights).where(
                    sa.and_(
                        services_access_rights.c.key == service_key,
                        services_access_rights.c.version == service_version,
                        services_access_rights.c.gid == group_id,
                        services_access_rights.c.product_name == product_name,
                    )
                )
            )
            row = result.one()

            # Track the entry for cleanup
            created_entries.append(
                (service_key, service_version, group_id, product_name)
            )

            # Convert row to dict
            return dict(row._asdict())

    yield creator

    # Cleanup all created entries
    with postgres_db.begin() as conn:
        for key, version, gid, product in created_entries:
            conn.execute(
                services_access_rights.delete().where(
                    sa.and_(
                        services_access_rights.c.key == key,
                        services_access_rights.c.version == version,
                        services_access_rights.c.gid == gid,
                        services_access_rights.c.product_name == product,
                    )
                )
            )
