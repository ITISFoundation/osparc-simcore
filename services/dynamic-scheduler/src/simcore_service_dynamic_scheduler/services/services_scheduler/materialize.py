from .models import DagTemplate, DbDirection, RunId


async def materialize_dag(*, run_id: RunId, direction: DbDirection, template: DagTemplate) -> None:
    # Placeholder: call repository functions to insert step_executions + step_deps
    _ = (run_id, direction, template)
