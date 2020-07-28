import uuid

from scheduler.api.io_models import ProjectUpdate
from scheduler.app import app
from scheduler.core.ingestion import workbench_updated
from scheduler.utils import get_tracking_log


@app.put("/workbench")
async def update_workbench(project_update: ProjectUpdate) -> str:
    dict_project_update = project_update.dict()

    dict_project_update["project_id"] = str(dict_project_update["project_id"])
    dict_project_update["tracking_id"] = str(uuid.uuid4())

    log = get_tracking_log(dict_project_update)
    log.debug("workbench update")

    await workbench_updated(dict_project_update)
    return ""
