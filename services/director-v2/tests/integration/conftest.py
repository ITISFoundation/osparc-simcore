from typing import Any, Callable, Dict, Iterator, List
from uuid import uuid4

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.projects import ProjectAtDB, ProjectType
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import projects


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

            returned_project = ProjectAtDB.parse_obj(result.first())
            created_project_ids.append(f"{returned_project.uuid}")
            return returned_project

    yield creator

    # cleanup
    with postgres_db.connect() as con:
        con.execute(projects.delete().where(projects.c.uuid.in_(created_project_ids)))


@pytest.fixture
def update_project_workbench_with_comp_tasks(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable]:
    def updator(project_uuid: str):
        with postgres_db.connect() as con:
            result = con.execute(
                projects.select().where(projects.c.uuid == project_uuid)
            )
            prj_row = result.first()
            prj_workbench = prj_row.workbench

            result = con.execute(
                comp_tasks.select().where(comp_tasks.c.project_id == project_uuid)
            )
            # let's get the results and run_hash
            for task_row in result:
                # pass these to the project workbench
                prj_workbench[task_row.node_id]["outputs"] = task_row.outputs
                prj_workbench[task_row.node_id]["runHash"] = task_row.run_hash

            con.execute(
                projects.update()  # pylint:disable=no-value-for-parameter
                .values(workbench=prj_workbench)
                .where(projects.c.uuid == project_uuid)
            )

    yield updator
