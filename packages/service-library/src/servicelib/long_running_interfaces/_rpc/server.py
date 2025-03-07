from abc import ABC, abstractmethod

from servicelib.rabbitmq import RPCRouter
from settings_library.rabbit import RabbitSettings

from ...rabbitmq import RabbitMQRPCClient
from .._models import (
    JobName,
    JobStatus,
    JobUniqueId,
    ResultModel,
    StartParams,
    UniqueRPCID,
)
from ._utils import get_rpc_namespace


class BaseServerJobInterface(ABC):
    """allows the server side jobs to be implemented however the user pleases"""

    @abstractmethod
    async def start(
        self, name: JobName, unique_id: JobUniqueId, **params: StartParams
    ) -> None:
        """used to start a jbo, raises AlreadyStartedError"""

    @abstractmethod
    async def remove(self, unique_id: JobUniqueId) -> None:
        """aborts and removes a job"""

    @abstractmethod
    async def status(self, unique_id: JobUniqueId) -> JobStatus:
        """returns the job's current status"""

    @abstractmethod
    async def result(self, unique_id: JobUniqueId) -> ResultModel:
        """provides the result of the job, raises NoResultIsAvailableError"""


class ServerRPCInterface:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        unique_rpc_id: UniqueRPCID,
        job_interface: BaseServerJobInterface,
    ) -> None:
        self.rabbit_settings = rabbit_settings
        self.job_interface = job_interface

        self._rabbitmq_rpc_server: RabbitMQRPCClient | None = None

        self._rpc_namespace = get_rpc_namespace(unique_rpc_id)

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
            router.expose()(handler)

        await self._rabbitmq_rpc_server.register_router(router, self._rpc_namespace)

    async def teardown(self) -> None:
        if self._rabbitmq_rpc_server is not None:
            await self._rabbitmq_rpc_server.close()

    async def start(
        self, name: JobName, unique_id: JobUniqueId, **params: StartParams
    ) -> None:
        await self.job_interface.start(name, unique_id, **params)

    async def remove(self, unique_id: JobUniqueId) -> None:
        await self.job_interface.remove(unique_id)

    async def status(self, unique_id: JobUniqueId) -> JobStatus:
        return await self.job_interface.status(unique_id)

    async def result(self, unique_id: JobUniqueId) -> ResultModel:
        return await self.job_interface.result(unique_id)
