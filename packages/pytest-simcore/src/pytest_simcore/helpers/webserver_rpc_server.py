# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.projects import ProjectID
from pydantic import TypeAdapter
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class WebserverRpcSideEffects:
    # pylint: disable=no-self-use

    async def mark_project_as_job(
        self,
        rpc_client: RabbitMQRPCClient,
        *,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
    ) -> None:
        assert rpc_client

        assert not job_parent_resource_name.startswith("/")  # nosec
        assert "/" in job_parent_resource_name  # nosec
        assert not job_parent_resource_name.endswith("/")  # nosec

        TypeAdapter(ProjectID).validate_python(project_uuid)
