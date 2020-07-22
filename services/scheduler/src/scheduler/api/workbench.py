from uuid import UUID, uuid4

from scheduler.api.io_models import TypeWorkbench
from scheduler.app import app
from scheduler.core.ingestion import workbench_updated


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


@app.post("workbench")
async def update_workbench(project_id: UUID, workbench: TypeWorkbench) -> str:
    await workbench_updated(project_id, workbench)
    return ""


@app.post("/mocking")
async def start_scheduler():
    """Endpoint used to test while developing """
    await workbench_updated(uuid4(), {})
    return ""
