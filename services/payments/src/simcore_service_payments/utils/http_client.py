import contextlib
import logging

import httpx
from fastapi import FastAPI

_logger = logging.getLogger(__name__)


class BaseHttpApi:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        # Controls all resources lifespan in sync
        self._exit_stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def _start(self):
        await self._exit_stack.enter_async_context(self.client)

    async def _close(self):
        await self._exit_stack.aclose()

    def attach_lifespan_to_app(self, app: FastAPI):
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


class AppStateMixin:
    """
    Mixin to load, save and delete from/to app.state
    """

    app_state_name: str
    frozen: bool = True

    @classmethod
    def load_from_state(cls, app: FastAPI):
        return getattr(app.state, cls.app_state_name)

    def save_to_state(self, app: FastAPI):
        if (exists := getattr(app.state, self.app_state_name, None)) and self.frozen:
            msg = f"An instance of {type(self)} already in app.state.{self.app_state_name}={exists}"
            raise ValueError(msg)

        setattr(app.state, self.app_state_name, self)
        return self.load_from_state(app)

    @classmethod
    def delete_from_state(cls, app: FastAPI):
        old = getattr(app.state, cls.app_state_name, None)
        delattr(app.state, cls.app_state_name)
        return old
