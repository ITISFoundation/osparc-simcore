from dataclasses import dataclass
from functools import partial

from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.storage.simcore_s3 import start_export_data

from ..exceptions.service_errors_utils import service_exception_mapper

_exception_mapper = partial(service_exception_mapper, service_name="Storage")


@dataclass(frozen=True, kw_only=True)
class StorageService:
    _rpc_client: RabbitMQRPCClient
    _user_id: UserID
    _product_name: ProductName

    @_exception_mapper(rpc_exception_map={})
    async def start_data_export(
        self,
        paths_to_export: list[PathToExport],
    ) -> AsyncJobGet:
        async_job_get, _ = await start_export_data(
            self._rpc_client,
            user_id=self._user_id,
            product_name=self._product_name,
            paths_to_export=paths_to_export,
            export_as="download_link",
        )
        return async_job_get
