import datetime
from typing import Any

from fastapi import FastAPI, status
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import AttachLifespanMixin, HasClientSetupInterface
from servicelib.fastapi.http_client_thin import UnexpectedStatusError
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)

from ._thin_client import DirectorV2ThinClient


class DirectorV2Client(
    SingletonInAppStateMixin, AttachLifespanMixin, HasClientSetupInterface
):
    app_state_name: str = "director_v2_client"

    def __init__(self, app: FastAPI) -> None:
        self.thin_client = DirectorV2ThinClient(app)

    async def setup_client(self) -> None:
        await self.thin_client.setup_client()

    async def teardown_client(self) -> None:
        await self.thin_client.teardown_client()

    async def get_status(
        self, node_id: NodeID
    ) -> NodeGet | DynamicServiceGet | NodeGetIdle:
        try:
            response = await self.thin_client.get_status(node_id)
            dict_response: dict[str, Any] = response.json()

            # in case of legacy version
            # we need to transfer the correct format!
            if "data" in dict_response:
                return TypeAdapter(NodeGet).validate_python(dict_response["data"])

            return TypeAdapter(DynamicServiceGet).validate_python(dict_response)
        except UnexpectedStatusError as e:
            if (
                e.response.status_code  # type: ignore[attr-defined] # pylint:disable=no-member
                == status.HTTP_404_NOT_FOUND
            ):
                return NodeGetIdle.from_node_id(node_id)
            raise

    async def run_dynamic_service(
        self, dynamic_service_start: DynamicServiceStart
    ) -> NodeGet | DynamicServiceGet:
        response = await self.thin_client.post_dynamic_service(dynamic_service_start)
        dict_response: dict[str, Any] = response.json()

        # legacy services
        if "data" in dict_response:
            return TypeAdapter(NodeGet).validate_python(dict_response["data"])

        return TypeAdapter(DynamicServiceGet).validate_python(dict_response)

    async def stop_dynamic_service(
        self,
        *,
        node_id: NodeID,
        simcore_user_agent: str,
        save_state: bool,
        timeout: datetime.timedelta
    ) -> None:
        try:
            await self.thin_client.delete_dynamic_service(
                node_id=node_id,
                simcore_user_agent=simcore_user_agent,
                save_state=save_state,
                timeout=timeout,
            )
        except UnexpectedStatusError as e:
            if (
                e.response.status_code  # type: ignore[attr-defined] # pylint:disable=no-member
                == status.HTTP_409_CONFLICT
            ):
                raise ServiceWaitingForManualInterventionError(
                    node_id=node_id
                ) from None
            if (
                e.response.status_code  # type: ignore[attr-defined] # pylint:disable=no-member
                == status.HTTP_404_NOT_FOUND
            ):
                raise ServiceWasNotFoundError(node_id=node_id) from None

            raise


def setup_director_v2(app: FastAPI) -> None:
    public_client = DirectorV2Client(app)
    public_client.thin_client.attach_lifespan_to(app)
    public_client.set_to_app_state(app)
