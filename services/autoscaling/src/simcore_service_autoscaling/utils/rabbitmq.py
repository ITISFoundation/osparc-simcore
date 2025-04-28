import asyncio
import logging
from typing import cast, overload

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

logger = logging.getLogger(__name__)


@overload
async def log_tasks_message(
    app: FastAPI, tasks: list[DockerTask], message: str, *, level: int = logging.INFO
) -> None: ...


@overload
async def log_tasks_message(
    app: FastAPI, tasks: list[DaskTask], message: str, *, level: int = logging.INFO
) -> None: ...


async def log_tasks_message(
    app: FastAPI,
    tasks: list[DockerTask] | list[DaskTask],
    message: str,
    *,
    level: int = logging.INFO,
) -> None:
    if not tasks:
        return
    if isinstance(tasks[0], DockerTask):
        await asyncio.gather(
            *(
                _post_task_log_message_from_docker_task(
                    app, cast(DockerTask, task), message, level
                )
                for task in tasks
            ),
            return_exceptions=True,
        )
    else:
        await asyncio.gather(
            *(
                _post_task_log_message_from_dask_task(
                    app, cast(DaskTask, task), message, level
                )
                for task in tasks
            ),
            return_exceptions=True,
        )


async def progress_tasks_message(
    app: FastAPI, tasks: list[DockerTask], progress: float
) -> None:
    await asyncio.gather(
        *(_post_task_progress_message(app, task, progress) for task in tasks),
        return_exceptions=True,
    )


async def _post_task_progress_message(
    app: FastAPI, task: DockerTask, progress: float
) -> None:
    with log_catch(logger, reraise=False):
        simcore_label_keys = StandardSimcoreDockerLabels.from_docker_task(task)
        message = ProgressRabbitMessageNode.model_construct(
            node_id=simcore_label_keys.node_id,
            user_id=simcore_label_keys.user_id,
            project_id=simcore_label_keys.project_id,
            progress_type=ProgressType.CLUSTER_UP_SCALING,
            report=ProgressReport(actual_value=progress, total=1),
        )
        await post_message(app, message)


async def _post_task_log_message_from_docker_task(
    app: FastAPI, task: DockerTask, log: str, level: int
) -> None:
    with log_catch(logger, reraise=False):
        simcore_label_keys = StandardSimcoreDockerLabels.from_docker_task(task)
        await _post_task_log_message(
            app,
            user_id=simcore_label_keys.user_id,
            project_id=simcore_label_keys.project_id,
            node_id=simcore_label_keys.node_id,
            log=log,
            level=level,
        )


async def _post_task_log_message_from_dask_task(
    app: FastAPI, task: DaskTask, log: str, level: int
) -> None:
    with log_catch(logger, reraise=False):
        (
            _service_key,
            _service_version,
            user_id,
            project_id,
            node_id,
        ) = parse_dask_job_id(task.task_id)
        await _post_task_log_message(
            app,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            log=log,
            level=level,
        )


async def _post_task_log_message(
    app: FastAPI,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    log: str,
    level: int,
) -> None:
    message = LoggerRabbitMessage.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        messages=[f"[cluster] {log}"],
        log_level=level,
    )
    logger.log(level, message)
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
        origin = f"dynamic:node_labels={app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS}"
    elif app_settings.AUTOSCALING_DASK:
        origin = f"computational:scheduler_url={app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL}"
    return RabbitAutoscalingStatusMessage.model_construct(
        origin=origin,
        nodes_total=len(cluster.active_nodes)
        + len(cluster.drained_nodes)
        + len(cluster.buffer_drained_nodes),
        nodes_active=len(cluster.active_nodes),
        nodes_drained=len(cluster.drained_nodes) + len(cluster.buffer_drained_nodes),
        cluster_total_resources=cluster_total_resources.model_dump(),
        cluster_used_resources=cluster_used_resources.model_dump(),
        instances_pending=len(cluster.pending_ec2s),
        instances_running=len(cluster.active_nodes)
        + len(cluster.drained_nodes)
        + len(cluster.buffer_drained_nodes),
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
