# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import logging
from pathlib import Path
from typing import Dict

import sqlalchemy as sa
from simcore_postgres_database.models.comp_tasks import comp_tasks

log = logging.getLogger(__name__)


def update_configuration(
    postgres_engine: sa.engine.Engine,
    project_id: str,
    node_uuid: str,
    new_configuration: Dict,
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


SIMCORE_STORE = "0"


def file_uuid(file_path: Path, project_id: str, node_uuid: str) -> str:
    file_id = f"{project_id}/{node_uuid}/{Path(file_path).name}"
    return file_id
