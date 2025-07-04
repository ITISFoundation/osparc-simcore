from enum import StrEnum

_TASK_QUEUE_PREFIX: str = "storage."


class TaskQueue(StrEnum):
    DEFAULT = f"{_TASK_QUEUE_PREFIX}.default"
    CPU_BOUND = f"{_TASK_QUEUE_PREFIX}.cpu_bound"
