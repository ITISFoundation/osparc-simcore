import contextlib
import functools
import logging
from dataclasses import dataclass, field

import httpx

_logger = logging.getLogger(__name__)


#
# TODO: compare with
# services/api-server/src/simcore_service_api_server/utils/app_data.py
# services/api-server/src/simcore_service_api_server/utils/client_base.py


def run_once(*, raise_for_rerun: bool = False):
    def _decorator(class_method):
        def _wrapper(cls, *args, **kwargs):
            if not _wrapper.has_run:
                _wrapper.has_run = True
                return class_method(cls, *args, **kwargs)

            msg = f"{class_method.__name__} has already been executed and will not run again."
            if raise_for_rerun:
                raise RuntimeError(msg)
            _logger.warning(msg)
            return None

        _wrapper.has_run = False
        return functools.wraps(_wrapper)

    return _decorator


@dataclass
class BaseHttpApi:
    client: httpx.AsyncClient
    _exit_stack: contextlib.AsyncExitStack = field(
        default_factory=contextlib.AsyncExitStack
    )

    async def start(self):
        await self._exit_stack.enter_async_context(self.client)

    async def close(self):
        await self._exit_stack.aclose()

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
