import uuid

from typing import Dict
from fastapi import HTTPException

from scheduler.api.io_models import ProjectActiveUpdate, ProjectUpdate
from scheduler.app import app
from scheduler.core.ingestion import workbench_updated
from scheduler.dbs.mongo_models.workbench import WorkbenchUpdate
from scheduler.utils import get_tracking_log


@app.put("/workbench")
async def update_workbench(project_update: ProjectUpdate) -> Dict:
    """To be called each time the workbench changes"""
    dict_project_update = project_update.dict()

    dict_project_update["project_id"] = str(dict_project_update["project_id"])
    dict_project_update["tracking_id"] = str(uuid.uuid4())

    log = get_tracking_log(dict_project_update)
    log.debug("workbench update")

    await workbench_updated(dict_project_update)
    return {}


@app.put("/workbench/active")
async def update_project_active(project_active_update: ProjectActiveUpdate) -> Dict:
    """When set to True it means that the project is currently opened in a browser window
    or being used by the API"""
    workbench_update = await WorkbenchUpdate.entry_for_project_id(
        project_active_update.project_id
    )

    if workbench_update is None:
        message = f"Could not find a project for provided project_id '{project_active_update.project_id}''"
        raise HTTPException(status_code=400, detail=message)

    await workbench_update.set_active(project_active_update.is_active)
    return {}
