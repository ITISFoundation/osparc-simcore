from dataclasses import dataclass
from datetime import timedelta

from models_library.progress_bar import ProgressReport

from ..models import (
    Task,
    TaskContext,
    TaskID,
    TaskMetadata,
    TaskUUID,
    build_task_id_prefix,
)


@dataclass
class MemoryTaskInfo:
    metadata: TaskMetadata
    progress: ProgressReport


class MemoryTaskInfoStore:
    def __init__(self) -> None:
        self._tasks: dict[TaskID, MemoryTaskInfo] = {}

    async def create_task(
        self,
        task_id: TaskID,
        task_metadata: TaskMetadata,
        expiry: timedelta,
    ) -> None:
        self._tasks[task_id] = MemoryTaskInfo(
            metadata=task_metadata,
            progress=ProgressReport(actual_value=0.0),
        )

    async def exists_task(self, task_id: TaskID) -> bool:
        return task_id in self._tasks

    async def get_task_metadata(self, task_id: TaskID) -> TaskMetadata | None:
        task_info = self._tasks.get(task_id)
        if task_info is None:
            return None
        return task_info.metadata

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None:
        task_info = self._tasks.get(task_id)
        if task_info is None:
            return None
        return task_info.progress

    async def list_tasks(self, task_context: TaskContext) -> list[Task]:
        tasks = []
        task_id_prefix = build_task_id_prefix(task_context)
        for task_id, task_info in self._tasks.items():
            if task_id.startswith(task_id_prefix):
                tasks.append(
                    Task(
                        uuid=TaskUUID(task_id[len(task_id_prefix) + 1 :]),
                        metadata=task_info.metadata,
                    )
                )
        return tasks

    async def remove_task(self, task_id: TaskID) -> None:
        self._tasks.pop(task_id, None)

    async def set_task_progress(self, task_id: TaskID, report: ProgressReport) -> None:
        task_info = self._tasks.get(task_id)
        if task_info is not None:
            task_info.progress = report
