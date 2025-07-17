# pylint: disable=no-self-use
# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.api_schemas_directorv2.computations import TaskLogFileIdGet
from models_library.projects import ProjectID
from pydantic import TypeAdapter, validate_call
from pytest_mock import MockType
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class DirectorV2SideEffects:
    # pylint: disable=no-self-use
    @validate_call(config={"arbitrary_types_allowed": True})
    async def get_computation_task_log_file_ids(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        project_id: ProjectID,
    ) -> list[TaskLogFileIdGet]:
        assert rpc_client
        assert project_id

        return TypeAdapter(list[TaskLogFileIdGet]).validate_python(
            TaskLogFileIdGet.model_json_schema()["examples"],
        )
