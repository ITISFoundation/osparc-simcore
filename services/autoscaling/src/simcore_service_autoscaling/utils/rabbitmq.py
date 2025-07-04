import asyncio
import logging

from aws_library.ec2 import Resources
from dask_task_models_library.container_tasks.utils import parse_dask_job_id
from fastapi import FastAPI
from models_library.docker import StandardSimcoreDockerLabels
from models_library.generated_models.docker_rest_api import Task as DockerTask
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressType,
    RabbitAutoscalingStatusMessage,
)
from models_library.users import UserID
from servicelib.logging_utils import log_catch

from ..core.settings import ApplicationSettings, get_application_settings
from ..models import Cluster, DaskTask
from ..modules.rabbitmq import post_message

_logger = logging.getLogger(__name__)


def _get_task_ids(task: DockerTask | DaskTask) -> tuple[UserID, ProjectID, NodeID]:
    if isinstance(task, DockerTask):
        labels = StandardSimcoreDockerLabels.from_docker_task(task)
        return labels.user_id, labels.project_id, labels.node_id
    _service_key, _service_version, user_id, project_id, node_id = parse_dask_job_id(
        task.task_id
    )
    return user_id, project_id, node_id


async def post_tasks_log_message(
    app: FastAPI,
    *,
    tasks: list[DockerTask] | list[DaskTask],
    message: str,
    level: int = logging.INFO,
) -> None:
    if not tasks:
        return

    with log_catch(_logger, reraise=False):
        await asyncio.gather(
            *(
                _post_task_log_message(
                    app,
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                    log=message,
                    level=level,
                )
                for user_id, project_id, node_id in (
                    _get_task_ids(task) for task in tasks
                )
            ),
            return_exceptions=True,
        )


async def post_tasks_progress_message(
    app: FastAPI,
    *,
    tasks: list[DockerTask] | list[DaskTask],
    progress: float,
    progress_type: ProgressType,
) -> None:
    if not tasks:
        return

    with log_catch(_logger, reraise=False):
        await asyncio.gather(
            *(
                _post_task_progress_message(
                    app,
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                    progress=progress,
                    progress_type=progress_type,
                )
                for user_id, project_id, node_id in (
                    _get_task_ids(task) for task in tasks
                )
            ),
            return_exceptions=True,
        )


async def _post_task_progress_message(
    app: FastAPI,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    progress: float,
    progress_type: ProgressType,
) -> None:
    message = ProgressRabbitMessageNode.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        progress_type=progress_type,
        report=ProgressReport(actual_value=progress, total=1),
    )
    await post_message(app, message)


async def _post_task_log_message(
    app: FastAPI,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    log: str,
    level: int,
) -> None:
    cluster_log = f"[cluster] {log}"
    _logger.log(level, cluster_log)

    message = LoggerRabbitMessage.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        messages=[cluster_log],
        log_level=level,
    )
    await post_message(app, message)


async def _create_autoscaling_status_message(
    app_settings: ApplicationSettings,
    cluster: Cluster,
    cluster_total_resources: Resources,
    cluster_used_resources: Resources,
) -> RabbitAutoscalingStatusMessage:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    origin = "unknown"
    if app_settings.AUTOSCALING_NODES_MONITORING:
        origin = f"dynamic:node_labels={app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS!s}"
    elif app_settings.AUTOSCALING_DASK:
        origin = f"computational:scheduler_url={app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL!s}"

    total_nodes = (
        len(cluster.active_nodes)
        + len(cluster.drained_nodes)
        + len(cluster.hot_buffer_drained_nodes)
    )
    drained_nodes = len(cluster.drained_nodes) + len(cluster.hot_buffer_drained_nodes)

    return RabbitAutoscalingStatusMessage.model_construct(
        origin=origin,
        nodes_total=total_nodes,
        nodes_active=len(cluster.active_nodes),
        nodes_drained=drained_nodes,
        cluster_total_resources=cluster_total_resources.model_dump(),
        cluster_used_resources=cluster_used_resources.model_dump(),
        instances_pending=len(cluster.pending_ec2s),
        instances_running=total_nodes,
    )


async def post_autoscaling_status_message(
    app: FastAPI,
    cluster: Cluster,
    cluster_total_resources: Resources,
    cluster_used_resources: Resources,
) -> None:
    await post_message(
        app,
        await _create_autoscaling_status_message(
            get_application_settings(app),
            cluster,
            cluster_total_resources,
            cluster_used_resources,
        ),
    )
