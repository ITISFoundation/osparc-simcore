import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Node, Task
from models_library.rabbitmq_messages import (
    AutoscalingStatus,
    LoggerRabbitMessage,
    RabbitAutoscalingMessage,
)
from servicelib.logging_utils import log_catch

from ..models import Resources, SimcoreServiceDockerLabelKeys
from ..modules.rabbitmq import post_message

logger = logging.getLogger(__name__)


async def post_state_message(
    app: FastAPI,
    monitored_nodes: list[Node],
    cluster_total_resources: Resources,
    cluster_used_resources: Resources,
    pending_tasks: list[Task],
) -> None:
    with log_catch(logger, reraise=False):
        message = RabbitAutoscalingMessage(
            origin=app.title,
            number_monitored_nodes=len(monitored_nodes),
            cluster_total_resources=cluster_total_resources.dict(),
            cluster_used_resources=cluster_used_resources.dict(),
            number_pending_tasks_without_resources=len(pending_tasks),
            status=AutoscalingStatus.SCALING_UP
            if pending_tasks
            else AutoscalingStatus.IDLE,
        )
        logger.debug("autoscaling state: %s", message)
        await post_message(app, message)


async def post_log_message(app: FastAPI, task: Task, log: str, level: int):
    with log_catch(logger, reraise=False):
        simcore_label_keys = SimcoreServiceDockerLabelKeys.from_docker_task(task)
        message = LoggerRabbitMessage(
            node_id=simcore_label_keys.node_id,
            user_id=simcore_label_keys.user_id,
            project_id=simcore_label_keys.project_id,
            messages=[log],
        )
        logger.log(level, message)
        await post_message(app, message)
