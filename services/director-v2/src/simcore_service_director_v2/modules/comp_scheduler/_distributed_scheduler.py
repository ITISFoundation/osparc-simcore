import datetime
from typing import Final

from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from servicelib.redis_utils import exclusive
from settings_library.redis import RedisDatabase
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
from simcore_service_director_v2.modules.rabbitmq import get_rabbitmq_client

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
    rabbitmq_client = get_rabbitmq_client(app)
    for run in runs_to_schedule:
        # TODO: we should use the transaction and the asyncpg engine here to ensure 100% consistency
        # async with transaction_context(get_asyncpg_engine(app)) as connection:
        await rabbitmq_client.publish(
            SchedulePipelineRabbitMessage.channel_name,
            SchedulePipelineRabbitMessage(
                user_id=run.user_id,
                project_id=run.project_uuid,
                iteration=run.iteration,
            ),
        )
        await CompRunsRepository.instance(db_engine).mark_as_scheduled(
            user_id=run.user_id, project_id=run.project_uuid, iteration=run.iteration
        )
