import asyncio
import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Availability, Task
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessage,
    ProgressType,
    RabbitAutoscalingStatusMessage,
)
from servicelib.logging_utils import log_catch

from ..core.settings import ApplicationSettings
from ..models import AssociatedInstance, EC2InstanceData, SimcoreServiceDockerLabelKeys
from ..modules.docker import AutoscalingDocker, get_docker_client
from ..modules.rabbitmq import post_message
from . import utils_docker

logger = logging.getLogger(__name__)


async def log_tasks_message(
    app: FastAPI, tasks: list[Task], message: str, *, level: int = logging.INFO
) -> None:
    await asyncio.gather(
        *(post_task_log_message(app, task, message, level) for task in tasks),
        return_exceptions=True,
    )


async def progress_tasks_message(
    app: FastAPI, tasks: list[Task], progress: float
) -> None:
    await asyncio.gather(
        *(post_task_progress_message(app, task, progress) for task in tasks),
        return_exceptions=True,
    )


async def post_task_progress_message(app: FastAPI, task: Task, progress: float) -> None:
    with log_catch(logger, reraise=False):
        simcore_label_keys = SimcoreServiceDockerLabelKeys.from_docker_task(task)
        message = ProgressRabbitMessage.construct(
            node_id=simcore_label_keys.node_id,
            user_id=simcore_label_keys.user_id,
            project_id=simcore_label_keys.project_id,
            progress_type=ProgressType.CLUSTER_UP_SCALING,
            progress=progress,
        )
        await post_message(app, message)


async def post_task_log_message(app: FastAPI, task: Task, log: str, level: int) -> None:
    with log_catch(logger, reraise=False):
        simcore_label_keys = SimcoreServiceDockerLabelKeys.from_docker_task(task)
        message = LoggerRabbitMessage.construct(
            node_id=simcore_label_keys.node_id,
            user_id=simcore_label_keys.user_id,
            project_id=simcore_label_keys.project_id,
            messages=[f"[cluster] {log}"],
            log_level=level,
        )
        logger.log(level, message)
        await post_message(app, message)


async def create_autoscaling_status_message(
    docker_client: AutoscalingDocker,
    app_settings: ApplicationSettings,
    attached_ec2s: list[AssociatedInstance],
    pending_ec2s: list[EC2InstanceData],
) -> RabbitAutoscalingStatusMessage:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    monitored_nodes = [i.node for i in attached_ec2s]
    (total_resources, used_resources) = await asyncio.gather(
        *(
            utils_docker.compute_cluster_total_resources(monitored_nodes),
            utils_docker.compute_cluster_used_resources(docker_client, monitored_nodes),
        )
    )
    return RabbitAutoscalingStatusMessage.construct(
        origin=f"{app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS}",
        nodes_total=len(monitored_nodes),
        nodes_active=len(
            [
                n
                for n in monitored_nodes
                if n.Spec and (n.Spec.Availability is Availability.active)
            ]
        ),
        nodes_drained=len(
            [
                n
                for n in monitored_nodes
                if n.Spec and (n.Spec.Availability is Availability.drain)
            ]
        ),
        cluster_total_resources=total_resources.dict(),
        cluster_used_resources=used_resources.dict(),
        instances_pending=len(pending_ec2s),
        instances_running=len(attached_ec2s),
    )


async def post_autoscaling_status_message(
    app: FastAPI,
    attached_ec2s: list[AssociatedInstance],
    pending_ec2s: list[EC2InstanceData],
) -> None:
    await post_message(
        app,
        await create_autoscaling_status_message(
            get_docker_client(app),
            app.state.settings,
            attached_ec2s,
            pending_ec2s,
        ),
    )
