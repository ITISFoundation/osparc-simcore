from datetime import timedelta

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel
from servicelib.base_distributed_identifier import BaseDistributedIdentifierManager
from servicelib.redis import RedisClientSDK

from ..director_v2 import api as director_v2_api

_CLEANUP_INTERVAL = timedelta(minutes=1)


class TrackerCleanupContext(BaseModel):
    simcore_user_agent: str
    save_state: bool


class ServicesManager(
    BaseDistributedIdentifierManager[
        NodeID,
        NodeGet | DynamicServiceGet | NodeGetIdle,
        TrackerCleanupContext,
    ]
):
    def __init__(self, app: FastAPI, redis_client_sdk: RedisClientSDK) -> None:
        super().__init__(redis_client_sdk, cleanup_interval=_CLEANUP_INTERVAL)
        self.app = app

    @classmethod
    def _deserialize_identifier(cls, raw: str) -> NodeID:
        return NodeID(raw)

    @classmethod
    def _serialize_identifier(cls, identifier: NodeID) -> str:
        return f"{identifier}"

    @classmethod
    def _deserialize_cleanup_context(cls, raw: str) -> TrackerCleanupContext:
        return TrackerCleanupContext.parse_raw(raw)

    @classmethod
    def _serialize_cleanup_context(cls, cleanup_context: TrackerCleanupContext) -> str:
        return cleanup_context.json()

    async def is_used(self, identifier: NodeID, _: TrackerCleanupContext) -> bool:
        service_status: NodeGet | DynamicServiceGet | NodeGetIdle = (
            await director_v2_api.get_service_status(self.app, node_id=identifier)
        )
        # NOTE: NodeGetIdle means the service is not present, it is stopped
        return not isinstance(service_status, NodeGetIdle)

    async def _create(  # pylint:disable=arguments-differ
        self, identifier: NodeID, rpc_dynamic_service_create: RPCDynamicServiceCreate
    ) -> tuple[NodeID, NodeGet | DynamicServiceGet | NodeGetIdle]:
        return (
            identifier,
            await director_v2_api.run_dynamic_service(
                self.app, rpc_dynamic_service_create=rpc_dynamic_service_create
            ),
        )

    async def get(  # pylint:disable=arguments-differ
        self, identifier: NodeID
    ) -> NodeGet | DynamicServiceGet | NodeGetIdle | None:
        # NOTE: does never return None
        return await director_v2_api.get_service_status(self.app, node_id=identifier)

    async def _destroy(
        self, identifier: NodeID, cleanup_context: TrackerCleanupContext
    ) -> None:
        await director_v2_api.stop_dynamic_service(
            self.app,
            node_id=identifier,
            simcore_user_agent=cleanup_context.simcore_user_agent,
            save_state=cleanup_context.save_state,
        )


async def get_service_status(
    services_manager: ServicesManager, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    service_status = await services_manager.get(identifier=node_id)
    assert service_status is not None  # nosec
    return service_status


async def run_dynamic_service(
    services_manager: ServicesManager,
    *,
    rpc_dynamic_service_create: RPCDynamicServiceCreate,
) -> NodeGet | DynamicServiceGet:
    _, status_after_creation = await services_manager.create(
        cleanup_context=TrackerCleanupContext(
            simcore_user_agent=rpc_dynamic_service_create.simcore_user_agent,
            save_state=rpc_dynamic_service_create.can_save,
        ),
        identifier=rpc_dynamic_service_create.node_uuid,
        rpc_dynamic_service_create=rpc_dynamic_service_create,
    )
    assert isinstance(status_after_creation, NodeGet | DynamicServiceGet)  # nosec
    return status_after_creation


async def stop_dynamic_service(
    services_manager: ServicesManager,
    *,
    node_id: NodeID,
    simcore_user_agent: str,
    save_state: bool,
) -> None:
    await services_manager.update_cleanup_context(
        identifier=node_id,
        cleanup_context=TrackerCleanupContext(
            simcore_user_agent=simcore_user_agent, save_state=save_state
        ),
    )

    await services_manager.remove(identifier=node_id, reraise=True)
