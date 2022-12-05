from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Node, Task
from models_library.rabbitmq_messages import AutoscalingStatus, RabbitAutoscalingMessage

from ..models import Resources


def create_rabbit_message(
    app: FastAPI,
    monitored_nodes: list[Node],
    cluster_total_resources: Resources,
    cluster_used_resources: Resources,
    pending_tasks: list[Task],
    status: AutoscalingStatus,
) -> RabbitAutoscalingMessage:
    return RabbitAutoscalingMessage(
        origin=app.title,
        number_monitored_nodes=len(monitored_nodes),
        cluster_total_resources=cluster_total_resources.dict(),
        cluster_used_resources=cluster_used_resources.dict(),
        number_pending_tasks_without_resources=len(pending_tasks),
        status=status,
    )
