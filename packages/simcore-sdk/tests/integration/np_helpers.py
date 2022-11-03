# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import logging

import sqlalchemy as sa
from simcore_postgres_database.models.comp_tasks import comp_tasks

log = logging.getLogger(__name__)


def update_configuration(
    postgres_engine: sa.engine.Engine,
    project_id: str,
    node_uuid: str,
    new_configuration: dict,
) -> None:
    log.debug(
        "Update configuration of pipeline %s, node %s",
        project_id,
        node_uuid,
    )

    with postgres_engine.connect() as conn:
        conn.execute(
            comp_tasks.update()  # pylint: disable=no-value-for-parameter
            .where(
                (comp_tasks.c.project_id == project_id)
                & (comp_tasks.c.node_id == node_uuid)
            )
            .values(
                schema=new_configuration["schema"],
                inputs=new_configuration["inputs"],
                outputs=new_configuration["outputs"],
            )
        )
    log.debug("Updated configuration")
