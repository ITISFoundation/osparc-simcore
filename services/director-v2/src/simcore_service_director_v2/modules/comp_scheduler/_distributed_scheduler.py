import datetime
from typing import Final

from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from servicelib.redis_utils import exclusive
from settings_library.redis import RedisDatabase

from ...core.settings import get_application_settings
from ...utils.comp_scheduler import SCHEDULED_STATES
from ..db import get_db_engine
from ..db.repositories.comp_runs import CompRunsRepository
from ..redis import get_redis_client_manager

_SCHEDULER_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)


def _redis_client_getter(*args, **kwargs) -> RedisClientSDK:
    assert kwargs is not None  # nosec
    app = args[0]
    assert isinstance(app, FastAPI)  # nosec
    return get_redis_client_manager(app).client(RedisDatabase.LOCKS)


@exclusive(_redis_client_getter, lock_key="computational-distributed-scheduler")
async def schedule_pipelines(app: FastAPI) -> None:
    app_settings = get_application_settings(app)
    db_engine = get_db_engine(app)
    runs_to_schedule = await CompRunsRepository.instance(db_engine).list(
        filter_by_state=SCHEDULED_STATES, scheduled_since=_SCHEDULER_INTERVAL
    )

    for run in runs_to_schedule:
        # await rpc_request_schedule_pipeline(run.user_id, run.project_uuid, run.iteration)
        pass
