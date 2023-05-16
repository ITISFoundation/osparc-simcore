# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter

from typing import Any, Callable, Iterator
from uuid import uuid4

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.projects import ProjectAtDB
from simcore_postgres_database.models.comp_pipeline import StateType, comp_pipeline
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.users import UserRole, UserStatus, users


@pytest.fixture()
def registered_user(
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
        return dict(user)

    yield creator

    with postgres_db.connect() as con:
        con.execute(users.delete().where(users.c.id.in_(created_user_ids)))
    print(f"<-- deleted users {created_user_ids=}")


@pytest.fixture
def project(
    postgres_db: sa.engine.Engine, faker: Faker
) -> Iterator[Callable[..., ProjectAtDB]]:
    created_project_ids: list[str] = []

    def creator(user: dict[str, Any], **overrides) -> ProjectAtDB:
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
        project_config.update(**overrides)
        with postgres_db.connect() as con:
            result = con.execute(
                projects.insert()
                .values(**project_config)
                .returning(sa.literal_column("*"))
            )

            inserted_project = ProjectAtDB.parse_obj(result.first())
        print(f"--> created {inserted_project=}")
        created_project_ids.append(f"{inserted_project.uuid}")
        return inserted_project

    yield creator

    # cleanup
    with postgres_db.connect() as con:
        con.execute(projects.delete().where(projects.c.uuid.in_(created_project_ids)))
    print(f"<-- delete projects {created_project_ids=}")


@pytest.fixture
def pipeline(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable[..., dict[str, Any]]]:
    created_pipeline_ids: list[str] = []

    def creator(**pipeline_kwargs) -> dict[str, Any]:
        pipeline_config = {
            "project_id": f"{uuid4()}",
            "dag_adjacency_list": {},
            "state": StateType.NOT_STARTED,
        }
        pipeline_config.update(**pipeline_kwargs)
        with postgres_db.connect() as conn:
            result = conn.execute(
                comp_pipeline.insert()
                .values(**pipeline_config)
                .returning(sa.literal_column("*"))
            )
            new_pipeline = result.first()
            assert new_pipeline
            new_pipeline = dict(new_pipeline)
            created_pipeline_ids.append(new_pipeline["project_id"])
            return new_pipeline

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_pipeline.delete().where(
                comp_pipeline.c.project_id.in_(created_pipeline_ids)
            )
        )
