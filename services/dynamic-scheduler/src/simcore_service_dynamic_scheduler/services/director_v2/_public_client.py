import datetime
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, status
from fastapi_lifespan_manager import State
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
    GetProjectInactivityResponse,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import AttachLifespanMixin
from servicelib.fastapi.http_client_thin import UnexpectedStatusError
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)

from ._thin_client import DirectorV2ThinClient


class DirectorV2Client(SingletonInAppStateMixin, AttachLifespanMixin):
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
        timeout: datetime.timedelta,  # noqa: ASYNC109
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
                    node_id=node_id,
                    unexpected_status_error=f"{e}",
                ) from None
            if (
                e.response.status_code  # type: ignore[attr-defined] # pylint:disable=no-member
                == status.HTTP_404_NOT_FOUND
            ):
                raise ServiceWasNotFoundError(node_id=node_id) from None

            raise

    async def retrieve_inputs(
        self,
        *,
        node_id: NodeID,
        port_keys: list[ServicePortKey],
        timeout: datetime.timedelta,  # noqa: ASYNC109
    ) -> RetrieveDataOutEnveloped:
        response = await self.thin_client.dynamic_service_retrieve(
            node_id=node_id, port_keys=port_keys, timeout=timeout
        )
        dict_response: dict[str, Any] = response.json()
        return TypeAdapter(RetrieveDataOutEnveloped).validate_python(dict_response)

    async def list_tracked_dynamic_services(
        self, *, user_id: UserID | None = None, project_id: ProjectID | None = None
    ) -> list[DynamicServiceGet]:
        response = await self.thin_client.get_dynamic_services(
            user_id=user_id, project_id=project_id
        )
        return TypeAdapter(list[DynamicServiceGet]).validate_python(response.json())

    async def get_project_inactivity(
        self, *, project_id: ProjectID, max_inactivity_seconds: NonNegativeInt
    ) -> GetProjectInactivityResponse:
        response = await self.thin_client.get_projects_inactivity(
            project_id=project_id, max_inactivity_seconds=max_inactivity_seconds
        )
        return TypeAdapter(GetProjectInactivityResponse).validate_python(
            response.json()
        )

    async def restart_user_services(self, *, node_id: NodeID) -> None:
        await self.thin_client.post_restart(node_id=node_id)

    async def update_projects_networks(self, *, project_id: ProjectID) -> None:
        await self.thin_client.patch_projects_networks(project_id=project_id)


async def director_v2_lifespan(app: FastAPI) -> AsyncIterator[State]:
    public_client = DirectorV2Client(app)
    public_client.set_to_app_state(app)

    yield {}

    public_client.pop_from_app_state(app)
