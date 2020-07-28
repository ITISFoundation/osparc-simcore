import logging
from typing import Any, Dict

from scheduler.dbs.mongo_models.workbench import WorkbenchUpdate
from scheduler.queues import QueueManager
from scheduler.utils import AsyncTaskWrapper, get_tracking_log

FIELDS_TO_REMOVE = {"position", "thumbnail"}


async def inject_other_data(raw_workbench: Dict[str, Any]) -> Any:
    # TODO: add all the necessary data the scheduler will need to
    # decide on where and how to schedule the services
    # make external calls to the director or other services which contain
    # this information
    return raw_workbench


def strip_entries_for_scheduling(workbench: Dict[str, Any],) -> Dict[str, Any]:
    for node_id, node_values in workbench.items():
        workbench[node_id] = {
            k: v for k, v in node_values.items() if k not in FIELDS_TO_REMOVE
        }
    return workbench


async def handle_updates_queue_input(project_update: Dict) -> None:
    """Creates a diff, if there are any differences, the messages
    is passed down the line for the pipeline to be updated"""
    log = get_tracking_log(project_update)
    log.debug("handle_updates_queue_input")

    # compute diffs and check if it needs scheduling
    ui_workbench = project_update["workbench"]
    scheduling_workbench = strip_entries_for_scheduling(ui_workbench.copy())

    # search for the project or create an entry if missing
    previous_update = await WorkbenchUpdate.entry_for_project_id(
        project_update["project_id"]
    )
    if previous_update is None:
        # create an entry and continue with the pipeline
        previous_update = await WorkbenchUpdate.create(
            project_id=project_update["project_id"],
            ui_workbench=ui_workbench,
            scheduling_workbench=scheduling_workbench,
        )
    # TODO: buffer changes while pipeline is "running"
    # recover them when the services have finished execution
    # and apply them to the to the pipeline
    # Not necessary for now as the UI is coordinated with backend
    # when integrating the API this will be required

    # check if changes ocurred
    should_pipeline_continue = previous_update.requires_pipeline_update(
        scheduling_workbench
    )

    await previous_update.insert_diff_if_required(
        new_scheduling_workbench=scheduling_workbench, new_ui_workbench=ui_workbench
    )
    if not should_pipeline_continue:
        log.info("Pipeline already up to date, will not trigger next steps")
        return

    # the scheduling workbench can now be enriched with more data
    # and passed to the next steps
    project_update["workbench"] = await inject_other_data(scheduling_workbench)

    async with QueueManager.get_enriched_workbenches() as enriched_workbenches_queue:
        log.info("pushing to enriched_workbenches_queue")
        await enriched_workbenches_queue.add(project_update)


async def enricher_worker() -> None:
    async with QueueManager.get_workbench_updates() as updates_queue:
        while True:
            message: Any = await updates_queue.get()
            await handle_updates_queue_input(message)


wrapped_enricher_worker = AsyncTaskWrapper(
    worker=enricher_worker, logger=logging.getLogger(__name__)
)
