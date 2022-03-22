from typing import Callable, Iterator

import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import projects


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
