# pylint: disable=no-self-use
# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Literal

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
)
from models_library.api_schemas_webserver.storage import PathToExport
from pydantic import TypeAdapter, validate_call
from pytest_mock import MockType
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class StorageSideEffects:
    # pylint: disable=no-self-use
    @validate_call(config={"arbitrary_types_allowed": True})
    async def start_export_data(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient | MockType,
        *,
        paths_to_export: list[PathToExport],
        export_as: Literal["path", "download_link"],
        job_filter: AsyncJobFilter,
    ) -> tuple[AsyncJobGet, AsyncJobFilter]:
        assert rabbitmq_rpc_client
        assert job_filter
        assert paths_to_export
        assert export_as

        async_job_get = TypeAdapter(AsyncJobGet).validate_python(
            AsyncJobGet.model_json_schema()["examples"][0],
        )
        async_job_filter = TypeAdapter(AsyncJobFilter).validate_python(
            AsyncJobFilter.model_json_schema()["examples"][0],
        )

        return async_job_get, async_job_filter
