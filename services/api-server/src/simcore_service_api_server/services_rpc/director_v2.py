from dataclasses import dataclass
from functools import partial

from models_library.projects import ProjectID
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.director_v2 import computations_tasks
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ComputationalTaskMissingError,
)

from ..exceptions.backend_errors import JobNotFoundError
from ..exceptions.service_errors_utils import service_exception_mapper

_exception_mapper = partial(service_exception_mapper, service_name="DirectorV2")


@dataclass(frozen=True, kw_only=True)
class DirectorV2Service:
    _rpc_client: RabbitMQRPCClient

    @_exception_mapper(
        rpc_exception_map={ComputationalTaskMissingError: JobNotFoundError}
    )
    async def get_computation_task_log_file_ids(self, *, project_id: ProjectID):
        return await computations_tasks.get_computation_task_log_file_ids(
            self._rpc_client, project_id=project_id
        )
