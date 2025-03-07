import logging
from typing import TypeVar

from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter
from settings_library.rabbit import RabbitSettings

from ...rabbitmq import RabbitMQRPCClient
from .._models import (
    JobStatus,
    JobUniqueId,
    LongRunningNamespace,
    ResultModel,
    StartParams,
)
from ._utils import get_rpc_namespace

_logger = logging.getLogger(__name__)


ResultType = TypeVar("ResultType")


class ClientRPCInterface:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        long_running_namespace: LongRunningNamespace,
    ) -> None:
        self.rabbit_settings = rabbit_settings

        self._rabbitmq_rpc_client: RabbitMQRPCClient | None = None
        self._rpc_namespace = get_rpc_namespace(long_running_namespace)

    async def setup(self) -> None:
        self._rabbitmq_rpc_client = await RabbitMQRPCClient.create(
            client_name="long_running_rpc_client", settings=self.rabbit_settings
        )

    async def teardown(self) -> None:
        if self._rabbitmq_rpc_client is not None:
            await self._rabbitmq_rpc_client.close()

    async def start(self, unique_id: JobUniqueId, **params: StartParams) -> None:
        assert self._rabbitmq_rpc_client  # nosec

        result = await self._rabbitmq_rpc_client.request(
            self._rpc_namespace,
            TypeAdapter(RPCMethodName).validate_python("start"),
            unique_id=unique_id,
            params=params,
        )
        assert result is None  # nosec

    async def remove(self, unique_id: JobUniqueId) -> None:
        """Cancels/aborts running job and removes it form remote worker"""
        assert self._rabbitmq_rpc_client  # nosec

        result = await self._rabbitmq_rpc_client.request(
            self._rpc_namespace,
            TypeAdapter(RPCMethodName).validate_python("remove"),
            unique_id=unique_id,
        )
        assert result is None  # nosec

    async def get_status(self, unique_id: JobUniqueId) -> JobStatus:
        assert self._rabbitmq_rpc_client  # nosec

        result = await self._rabbitmq_rpc_client.request(
            self._rpc_namespace,
            TypeAdapter(RPCMethodName).validate_python("status"),
            unique_id=unique_id,
        )
        assert isinstance(result, JobStatus)  # nosec
        return result

    async def get_result(self, unique_id: JobUniqueId) -> ResultModel:
        assert self._rabbitmq_rpc_client  # nosec

        result = await self._rabbitmq_rpc_client.request(
            self._rpc_namespace,
            TypeAdapter(RPCMethodName).validate_python("result"),
            unique_id=unique_id,
        )
        assert isinstance(result, ResultModel)  # nosec
        return result
