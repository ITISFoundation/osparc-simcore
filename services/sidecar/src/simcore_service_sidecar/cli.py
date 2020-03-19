import logging

import click

from .utils import wrap_async_call

log = logging.getLogger(__name__)


@click.command()
@click.option("--job_id", default="0", help="The job ID")
@click.option("--user_id", default="0", help="The user ID")
@click.option("--project_id", default="0", help="The project ID")
@click.option("--node_id", default=None, help="The node ID or nothing")
def main(job_id: str, user_id: str, project_id: str, node_id: str):
    from simcore_service_sidecar.core import SIDECAR
    import pdb; pdb.set_trace()
    log.info(
        "STARTING task processing for user %s, project %s, node %s",
        user_id,
        project_id,
        node_id,
    )
    try:
        next_task_nodes =  wrap_async_call(SIDECAR.inspect(job_id, user_id, project_id, node_id=node_id))
    except Exception: # pylint: disable=broad-except
        log.exception("Uncaught exception")
    log.info(
        "COMPLETED task processing for user %s, project %s, node %s",
        user_id,
        project_id,
        node_id,
    )
