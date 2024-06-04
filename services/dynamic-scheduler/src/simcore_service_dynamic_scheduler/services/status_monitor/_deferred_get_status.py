import logging
from datetime import timedelta

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from servicelib.deferred_tasks import BaseDeferredHandler, TaskUID
from servicelib.deferred_tasks._base_deferred_handler import DeferredContext

from ..director_v2 import DirectorV2Client
from ..service_tracker import (
    remove_tracked,
    set_new_status,
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

        _logger.debug("CALLED ON RESULT %s %s", node_id, result)

        # TOOD: maybe move all this logic tot the service_tracker

        # TODO: this should be transformed in set_new_status_if_changed
        # also this should return a "bool" if the status changed form the previous
        # this allows us to figure out when to send to the FE notifications
        # TODO: from here we need to add an integration with the module sending via webseocket
        # the status to the fronted
        await set_new_status(app, node_id, result)

        # remove service if no longer running
        if isinstance(result, NodeGetIdle):
            await remove_tracked(app, node_id)
