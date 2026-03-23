"""Nodes RPC API subclient."""

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import TypeAdapter

from ._base import BaseRpcApi


class NodesRpcApi(BaseRpcApi):
    async def get_node_service_key_version(
        self, *, project_id: ProjectID, node_id: NodeID
    ) -> tuple[ServiceKey, ServiceVersion]:
        result = await self._rpc_client.request(
            self._namespace,
            "get_node_service_key_version",
            project_id=project_id,
            node_id=node_id,
        )
        return TypeAdapter(tuple[ServiceKey, ServiceVersion]).validate_python(result)
