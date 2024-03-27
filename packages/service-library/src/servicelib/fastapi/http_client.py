import contextlib
import logging
from abc import ABC, abstractmethod

import httpx
from fastapi import FastAPI
from models_library.healthchecks import IsNonResponsive, IsResponsive, LivenessResult

from ..logging_utils import log_context

_logger = logging.getLogger(__name__)


class HasClientInterface(ABC):
    @property
    @abstractmethod
    def client(self) -> httpx.AsyncClient: ...


class HasClientSetupInterface(ABC):
    @abstractmethod
    async def setup_client(self) -> None: ...

    @abstractmethod
    async def teardown_client(self) -> None: ...


class BaseHTTPApi(HasClientSetupInterface):
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        # Controls all resources lifespan in sync
        self._exit_stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

    @classmethod
    def from_client_kwargs(cls, **kwargs):
        return cls(client=httpx.AsyncClient(**kwargs))

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def setup_client(self) -> None:
        with log_context(_logger, logging.INFO, "setup client"):
            await self._exit_stack.enter_async_context(self.client)

    async def teardown_client(self) -> None:
        with log_context(_logger, logging.INFO, "teardown client"):
            await self._exit_stack.aclose()


class AttachLifespanMixin(HasClientSetupInterface):
    def attach_lifespan_to(self, app: FastAPI) -> None:
        app.add_event_handler("startup", self.setup_client)
        app.add_event_handler("shutdown", self.teardown_client)


class HealthMixinMixin(HasClientInterface):
    async def ping(self) -> bool:
        """Check whether server is reachable"""
        try:
            await self.client.get("/")
            return True
        except httpx.RequestError:
            return False

    async def is_healthy(self) -> bool:
        """Service is reachable and ready"""
        try:
            response = await self.client.get("/")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def check_liveness(self) -> LivenessResult:
        try:
            response = await self.client.get("/")
            return IsResponsive(elapsed=response.elapsed)
        except httpx.RequestError as err:
            return IsNonResponsive(reason=f"{err}")
