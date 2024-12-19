from collections.abc import Callable

from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from models_library.projects_state import RunningState
from models_library.services_resources import (
    ResourceValue,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase

from ...models.comp_tasks import CompTaskAtDB
from ..redis import get_redis_client_manager

SCHEDULED_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
    RunningState.WAITING_FOR_CLUSTER,
}

TASK_TO_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.WAITING_FOR_CLUSTER,
}

WAITING_FOR_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.WAITING_FOR_CLUSTER,
}

PROCESSING_STATES: set[RunningState] = {
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
}

RUNNING_STATES: set[RunningState] = {
    RunningState.STARTED,
}

COMPLETED_STATES: set[RunningState] = {
    RunningState.ABORTED,
    RunningState.SUCCESS,
    RunningState.FAILED,
}


def create_service_resources_from_task(task: CompTaskAtDB) -> ServiceResourcesDict:
    assert task.image.node_requirements  # nosec
    return ServiceResourcesDictHelpers.create_from_single_service(
        DockerGenericTag(f"{task.image.name}:{task.image.tag}"),
        {
            res_name: ResourceValue(limit=res_value, reservation=res_value)
            for res_name, res_value in task.image.node_requirements.model_dump(
                by_alias=True
            ).items()
            if res_value is not None
        },
        [task.image.boot_mode],
    )


def _get_app_from_args(*args, **kwargs) -> FastAPI:
    assert kwargs is not None  # nosec
    if args:
        app = args[0]
    else:
        assert "app" in kwargs  # nosec
        app = kwargs["app"]
    assert isinstance(app, FastAPI)  # nosec
    return app


def get_redis_client_from_app(*args, **kwargs) -> RedisClientSDK:
    app = _get_app_from_args(*args, **kwargs)
    return get_redis_client_manager(app).client(RedisDatabase.LOCKS)


def get_redis_lock_key(
    suffix: str, *, unique_lock_key_builder: Callable[..., str] | None
) -> Callable[..., str]:
    def _(*args, **kwargs) -> str:
        app = _get_app_from_args(*args, **kwargs)
        unique_lock_part = (
            unique_lock_key_builder(*args, **kwargs) if unique_lock_key_builder else ""
        )
        if unique_lock_part:
            unique_lock_part = f"-{unique_lock_part}"
        return f"{app.title}-{suffix}{unique_lock_part}"

    return _
