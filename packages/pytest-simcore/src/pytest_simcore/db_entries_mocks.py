from typing import Any, Callable, Dict, Iterator, List
from uuid import uuid4

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.projects import ProjectAtDB
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.users import UserRole, UserStatus, users


@pytest.fixture()
def registered_user(
    postgres_db: sa.engine.Engine, faker: Faker
) -> Iterator[Callable[..., Dict]]:
    created_user_ids = []

    def creator(**user_kwargs) -> Dict[str, Any]:
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
                sa.select([users]).where(users.c.id == user_config["id"])
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
    created_project_ids: List[str] = []

    def creator(user: Dict[str, Any], **overrides) -> ProjectAtDB:
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
