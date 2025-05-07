import traceback
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any

from servicelib.rabbitmq import RPCRouter
from settings_library.rabbit import RabbitSettings

from ...rabbitmq import RabbitMQRPCClient
from .._errors import AlreadyStartedError, JobNotFoundError, NoResultIsAvailableError
from .._models import (
    ErrorModel,
    JobStatus,
    JobUniqueId,
    LongRunningNamespace,
    RemoteHandlerName,
    ResultModel,
    StartParams,
)
from ._utils import get_rpc_namespace


class BaseServerJobInterface(ABC):
    """allows the server side jobs to be implemented however the user pleases"""

    @abstractmethod
    async def start(
        self,
        name: RemoteHandlerName,
        unique_id: JobUniqueId,
        params: StartParams,
        timeout: timedelta,  # noqa: ASYNC109
    ) -> None:
        """used to start a job"""

    @abstractmethod
    async def remove(self, unique_id: JobUniqueId) -> None:
        """aborts and removes a job"""

    @abstractmethod
    async def is_present(self, unique_id: JobUniqueId) -> bool:
        """returns True if the job exists"""

    @abstractmethod
    async def is_running(self, unique_id: JobUniqueId) -> bool:
        """returns True if the job is currently running"""

    @abstractmethod
    async def get_result(self, unique_id: JobUniqueId) -> Any | None:
        """provides the result of the job once finished"""


class ServerRPCInterface:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        long_running_namespace: LongRunningNamespace,
        job_interface: BaseServerJobInterface,
    ) -> None:
        self.rabbit_settings = rabbit_settings
        self.job_interface = job_interface

        self._rabbitmq_rpc_server: RabbitMQRPCClient | None = None

        self._rpc_namespace = get_rpc_namespace(long_running_namespace)

    async def setup(self) -> None:
        self._rabbitmq_rpc_server = await RabbitMQRPCClient.create(
            client_name="long_running_rpc_server", settings=self.rabbit_settings
        )

        # expose RPC endpoints
        router = RPCRouter()
        for handler in (
            self.start,
            self.remove,
            self.status,
            self.result,
        ):
            router.expose(
                reraise_if_error_type=(JobNotFoundError, NoResultIsAvailableError)
            )(handler)

        await self._rabbitmq_rpc_server.register_router(router, self._rpc_namespace)

    async def teardown(self) -> None:
        if self._rabbitmq_rpc_server is not None:
            await self._rabbitmq_rpc_server.close()

    async def start(
        self,
        name: RemoteHandlerName,
        unique_id: JobUniqueId,
        params: StartParams,
        timeout: timedelta,  # noqa: ASYNC109
    ) -> None:
        if await self.job_interface.is_present(unique_id):
            raise AlreadyStartedError(unique_id=unique_id)

        await self.job_interface.start(name, unique_id, params, timeout)

    async def remove(self, unique_id: JobUniqueId) -> None:
        if await self.job_interface.is_present(unique_id):
            await self.job_interface.remove(unique_id)

    async def status(self, unique_id: JobUniqueId) -> JobStatus:
        if not await self.job_interface.is_present(unique_id):
            return JobStatus.NOT_FOUND

        if await self.job_interface.is_running(unique_id):
            return JobStatus.RUNNING

        return JobStatus.FINISHED

    async def result(self, unique_id: JobUniqueId) -> ResultModel:
        if not await self.job_interface.is_present(unique_id):
            raise JobNotFoundError(unique_id=unique_id)

        if await self.job_interface.is_running(unique_id):
            raise NoResultIsAvailableError(unique_id=unique_id)

        try:
            result = await self.job_interface.get_result(unique_id)
            return ResultModel(data=result)
        except Exception as e:  # pylint:disable=broad-exception-caught
            formatted_traceback = "\n".join(traceback.format_tb(e.__traceback__))
            return ResultModel(
                error=ErrorModel(
                    error_type=type(e),
                    error_message=f"{e}",
                    traceback=formatted_traceback,
                )
            )
