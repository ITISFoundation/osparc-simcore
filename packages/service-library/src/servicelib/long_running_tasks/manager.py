import datetime
from abc import ABC, abstractmethod

from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

from ..rabbitmq._client_rpc import RabbitMQRPCClient
from ._rabbit_namespace import get_rabbit_namespace
from ._rpc_server import router
from .models import LRTNamespace, TaskContext
from .task import TasksManager


class LongRunningManager(ABC):
    """
    Provides a commond inteface for aiohttp and fastapi services
    """

    def __init__(
        self,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
        redis_settings: RedisSettings,
        rabbit_settings: RabbitSettings,
        lrt_namespace: LRTNamespace,
    ):
        self._tasks_manager = TasksManager(
            stale_task_check_interval=stale_task_check_interval,
            stale_task_detect_timeout=stale_task_detect_timeout,
            redis_settings=redis_settings,
            lrt_namespace=lrt_namespace,
        )
        self._lrt_namespace = lrt_namespace
        self.rabbit_settings = rabbit_settings
        self._rpc_server: RabbitMQRPCClient | None = None
        self._rpc_client: RabbitMQRPCClient | None = None

    @property
    def tasks_manager(self) -> TasksManager:
        return self._tasks_manager

    @property
    def rpc_server(self) -> RabbitMQRPCClient:
        assert self._rpc_server is not None  # nosec
        return self._rpc_server

    @property
    def rpc_client(self) -> RabbitMQRPCClient:
        assert self._rpc_client is not None  # nosec
        return self._rpc_client

    @property
    def lrt_namespace(self) -> LRTNamespace:
        return self._lrt_namespace

    async def setup(self) -> None:
        await self._tasks_manager.setup()
        self._rpc_server = await RabbitMQRPCClient.create(
            client_name=f"lrt-server-{self.lrt_namespace}",
            settings=self.rabbit_settings,
        )
        self._rpc_client = await RabbitMQRPCClient.create(
            client_name=f"lrt-client-{self.lrt_namespace}",
            settings=self.rabbit_settings,
        )

        await self.rpc_server.register_router(
            router,
            get_rabbit_namespace(self.lrt_namespace),
            self,
        )

    async def teardown(self) -> None:
        await self._tasks_manager.teardown()

        if self._rpc_server is not None:
            await self._rpc_server.close()
            self._rpc_server = None

        if self._rpc_client is not None:
            await self._rpc_client.close()
            self._rpc_client = None

    @staticmethod
    @abstractmethod
    def get_task_context(request) -> TaskContext:
        """return the task context based on the current request"""
