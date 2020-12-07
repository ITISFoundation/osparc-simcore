# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import logging
from pathlib import Path
from typing import Dict

import sqlalchemy as sa
from simcore_sdk.models.pipeline_models import ComputationalTask

log = logging.getLogger(__name__)


def update_configuration(
    postgres_session: sa.orm.session.Session,
    project_id: str,
    node_uuid: str,
    new_configuration: Dict,
) -> None:
    log.debug(
        "Update configuration of pipeline %s, node %s, on session %s",
        project_id,
        node_uuid,
        postgres_session,
    )
    # pylint: disable=no-member
    task = postgres_session.query(ComputationalTask).filter(
        ComputationalTask.project_id == str(project_id),
        ComputationalTask.node_id == str(node_uuid),
    )
    task.update(
        dict(
            schema=new_configuration["schema"],
            inputs=new_configuration["inputs"],
            outputs=new_configuration["outputs"],
        )
    )
    postgres_session.commit()
    log.debug("Updated configuration")


SIMCORE_STORE = "0"


def file_uuid(file_path: Path, project_id: str, node_uuid: str) -> str:
    file_id = f"{project_id}/{node_uuid}/{Path(file_path).name}"
    return file_id
