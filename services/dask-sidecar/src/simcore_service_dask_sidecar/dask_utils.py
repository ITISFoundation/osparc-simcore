from dask_task_models_library.container_tasks.events import TaskEvent
from distributed import Pub


def publish_event(dask_pub: Pub, event: TaskEvent) -> None:
    dask_pub.put(event.json())
