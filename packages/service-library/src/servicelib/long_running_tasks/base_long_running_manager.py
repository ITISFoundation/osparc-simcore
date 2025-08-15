from abc import ABC, abstractmethod

from ..rabbitmq._client_rpc import RabbitMQRPCClient
from .models import RabbitNamespace
from .task import TasksManager


class BaseLongRunningManager(ABC):
    """
    Provides a commond inteface for aiohttp and fastapi services
    """

    @property
    @abstractmethod
    def tasks_manager(self) -> TasksManager:
        pass

    @property
    @abstractmethod
    def rpc_server(self) -> RabbitMQRPCClient:
        pass

    @property
    @abstractmethod
    def rabbit_namespace(self) -> RabbitNamespace:
        pass

    @abstractmethod
    async def setup(self) -> None:
        pass

    @abstractmethod
    async def teardown(self) -> None:
        pass
