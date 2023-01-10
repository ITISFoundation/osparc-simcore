import asyncio
import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Availability, Node, Task
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    RabbitAutoscalingStatusMessage,
)
from servicelib.logging_utils import log_catch

from ..core.settings import ApplicationSettings
from ..models import SimcoreServiceDockerLabelKeys
from ..modules.docker import AutoscalingDocker
from ..modules.ec2 import AutoscalingEC2
from ..modules.rabbitmq import post_message
from . import ec2, utils_docker

logger = logging.getLogger(__name__)


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
    total_resources, used_resources, all_ec2_instances = await asyncio.gather(
        *(
            utils_docker.compute_cluster_total_resources(monitored_nodes),
            utils_docker.compute_cluster_used_resources(docker_client, monitored_nodes),
            ec2_client.get_all_pending_running_instances(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                list(
                    ec2.get_ec2_tags(app_settings.AUTOSCALING_NODES_MONITORING).keys()
                ),
            ),
        )
    )
    pending_instances = [i for i in all_ec2_instances if i.state == "pending"]
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
        instances_pending=len(pending_instances),
        instances_running=len(all_ec2_instances) - len(pending_instances),
    )
