import logging
from datetime import timedelta

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from servicelib.deferred_tasks import BaseDeferredHandler, TaskUID
from servicelib.deferred_tasks._base_deferred_handler import DeferredContext

from ..director_v2 import DirectorV2Client
from ..notifier import notify_frontend
from ..service_tracker import (
    can_notify_frontend,
    remove_tracked,
    set_if_status_changed,
    set_service_status_task_uid,
)

_logger = logging.getLogger(__name__)


class DeferredGetStatus(BaseDeferredHandler[NodeGet | DynamicServiceGet | NodeGetIdle]):
    @classmethod
    async def get_timeout(cls, context: DeferredContext) -> timedelta:
        assert context  # nosec
        return timedelta(seconds=5)

    @classmethod
    async def start(  # pylint:disable=arguments-differ
        cls, node_id: NodeID
    ) -> DeferredContext:
        _logger.debug("Getting service status for %s", node_id)
        return {"node_id": node_id}

    @classmethod
    async def on_created(cls, task_uid: TaskUID, context: DeferredContext) -> None:
        """called after deferred was scheduled to run"""
        app: FastAPI = context["app"]
        node_id: NodeID = context["node_id"]

        await set_service_status_task_uid(app, node_id, task_uid)

    @classmethod
    async def run(
        cls, context: DeferredContext
    ) -> NodeGet | DynamicServiceGet | NodeGetIdle:
        app: FastAPI = context["app"]
        node_id: NodeID = context["node_id"]

        director_v2_client = DirectorV2Client.get_from_app_state(app)
        service_status = await director_v2_client.get_status(node_id)
        _logger.debug(
            "Service status type=%s, %s", type(service_status), service_status
        )
        return service_status

    @classmethod
    async def on_result(
        cls, result: NodeGet | DynamicServiceGet | NodeGetIdle, context: DeferredContext
    ) -> None:
        app: FastAPI = context["app"]
        node_id: NodeID = context["node_id"]

        _logger.debug("Received status for service '%s': '%s'", node_id, result)

        status_changed: bool = await set_if_status_changed(app, node_id, result)
        if await can_notify_frontend(app, node_id, status_changed=status_changed):
            await notify_frontend(app, node_id, result)

        # remove service if no longer running
        if isinstance(result, NodeGetIdle):
            await remove_tracked(app, node_id)
