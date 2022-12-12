import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Task
from models_library.rabbitmq_messages import LoggerRabbitMessage
from servicelib.logging_utils import log_catch

from ..models import SimcoreServiceDockerLabelKeys
from ..modules.rabbitmq import post_message

logger = logging.getLogger(__name__)


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
