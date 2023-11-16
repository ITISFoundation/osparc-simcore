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


class AppStateMixin:
    """
    Mixin to get, set and delete an instance of 'self' from/to app.state
    """

    app_state_name: str  # Name used in app.state.$(app_state_name)
    frozen: bool = True  # Will raise if set multiple times

    @classmethod
    def get_from_app_state(cls, app: FastAPI):
        return getattr(app.state, cls.app_state_name)

    def set_to_app_state(self, app: FastAPI):
        if (exists := getattr(app.state, self.app_state_name, None)) and self.frozen:
            msg = f"An instance of {type(self)} already in app.state.{self.app_state_name}={exists}"
            raise ValueError(msg)

        setattr(app.state, self.app_state_name, self)
        return self.get_from_app_state(app)

    @classmethod
    def pop_from_app_state(cls, app: FastAPI):
        old = getattr(app.state, cls.app_state_name, None)
        delattr(app.state, cls.app_state_name)
        return old


def to_curl_command(request: httpx.Request) -> str:
    """Composes a curl command from a given request

    Can be used to reproduce a request in a separate terminal (e.g. debugging)
    """
    # Adapted from https://github.com/marcuxyz/curlify2/blob/master/curlify2/curlify.py
    headers = [f'"{k}: {v}"' for k, v in request.headers.items()]
    method = request.method
    url = request.url
    body = request.read().decode()
    return f"curl -X {method} -H {' -H '.join(headers)} -d '{body}' {url}"
