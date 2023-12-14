import contextlib
import logging

import httpx
from fastapi import FastAPI
from models_library.healthchecks import IsNonResponsive, IsResponsive, LivenessResult

_logger = logging.getLogger(__name__)


class BaseHttpApi:
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

    async def _start(self):
        await self._exit_stack.enter_async_context(self.client)

    async def _close(self):
        await self._exit_stack.aclose()

    def attach_lifespan_to(self, app: FastAPI):
        app.add_event_handler("startup", self._start)
        app.add_event_handler("shutdown", self._close)

    #
    # service diagnostics
    #
    async def ping(self) -> bool:
        """Check whether server is reachable"""
        try:
            await self.client.get("/")
            return True
        except httpx.RequestError:
            return False

    async def is_healhy(self) -> bool:
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
