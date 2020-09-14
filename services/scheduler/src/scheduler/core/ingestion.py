from typing import Dict

from scheduler.queues import QueueManager


async def workbench_updated(project_update: Dict) -> None:
    async with QueueManager.get_workbench_updates() as workbench_updates:
        await workbench_updates.add(project_update)
