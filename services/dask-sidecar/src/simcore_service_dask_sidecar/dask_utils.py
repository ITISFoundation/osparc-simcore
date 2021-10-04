from dask_task_models_library.container_tasks.events import TaskEvent
from distributed.worker import get_client


def publish_event(event: TaskEvent) -> None:
    get_client().log_event(
        event.topic_name(),
        event.json(),
    )
