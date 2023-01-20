import asyncio
import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Availability, Node, Task
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessage,
    ProgressType,
    RabbitAutoscalingStatusMessage,
)
from servicelib.logging_utils import log_catch

from ..core.settings import ApplicationSettings
from ..models import SimcoreServiceDockerLabelKeys
from ..modules.docker import AutoscalingDocker, get_docker_client
from ..modules.ec2 import AutoscalingEC2, get_ec2_client
from ..modules.rabbitmq import post_message
from . import ec2, utils_docker

logger = logging.getLogger(__name__)


async def post_task_progress_message(app: FastAPI, task: Task, progress: float) -> None:
    with log_catch(logger, reraise=False):
        simcore_label_keys = SimcoreServiceDockerLabelKeys.from_docker_task(task)
        message = ProgressRabbitMessage(
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
        message = LoggerRabbitMessage(
            node_id=simcore_label_keys.node_id,
            user_id=simcore_label_keys.user_id,
            project_id=simcore_label_keys.project_id,
            messages=[f"[cluster] {log}"],
        )
        logger.log(level, message)
        await post_message(app, message)


async def create_autoscaling_status_message(
    docker_client: AutoscalingDocker,
    ec2_client: AutoscalingEC2,
    app_settings: ApplicationSettings,
    monitored_nodes: list[Node],
) -> RabbitAutoscalingStatusMessage:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    (
        total_resources,
        used_resources,
        pending_ec2_instances,
        running_ec2_instances,
    ) = await asyncio.gather(
        *(
            utils_docker.compute_cluster_total_resources(monitored_nodes),
            utils_docker.compute_cluster_used_resources(docker_client, monitored_nodes),
            ec2_client.get_instances(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                list(
                    ec2.get_ec2_tags(app_settings.AUTOSCALING_NODES_MONITORING).keys()
                ),
                state_names=["pending"],
            ),
            ec2_client.get_instances(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                list(
                    ec2.get_ec2_tags(app_settings.AUTOSCALING_NODES_MONITORING).keys()
                ),
                state_names=["running"],
            ),
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
        instances_pending=len(pending_ec2_instances),
        instances_running=len(running_ec2_instances),
    )


async def post_autoscaling_status_message(
    app: FastAPI, monitored_nodes: list[Node]
) -> None:
    await post_message(
        app,
        await create_autoscaling_status_message(
            get_docker_client(app),
            get_ec2_client(app),
            app.state.settings,
            monitored_nodes,
        ),
    )
