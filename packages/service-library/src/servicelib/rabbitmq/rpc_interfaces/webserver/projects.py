import logging

from models_library.projects import ProjectID
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def mark_project_as_job(
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

    raise NotImplementedError
