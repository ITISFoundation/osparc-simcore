import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional

from aiohttp import web
from aiosignal import Signal

from ._constants import APP_SETTINGS_KEY

_HeathCheckSignal = Signal[Callable[[web.Application], Awaitable[None]]]


class HeathCheckError(web.HTTPServiceUnavailable):
    """Service is set as unhealty"""


class HeathCheck:
    def __init__(self):
        self._on_healthcheck = Signal(owner=self)  # type: _HeathCheckSignal

    @property
    def on_healthcheck(self) -> _HeathCheckSignal:
        return self._on_healthcheck

    @staticmethod
    def get_app_info(app: web.Application):
        # TODO: could get some info from app.settings
        settings = app[APP_SETTINGS_KEY]

        return {
            "name": settings.API_NAME,
            "version": settings.API_VERSION,
            "api_version": settings.API_VERSION,
        }

    async def run(
        self, app: web.Application, *, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Runs healtcheck with a timeout [secs]"""
        # ensures no more signals append after first run
        self._on_healthcheck.freeze()

        try:
            heath_report = self.get_app_info(app)

            # TODO: every signal could return some info on the health on each part
            # that is appended on heath_report
            await asyncio.wait_for(self._on_healthcheck.send(app), timeout=timeout)

        except asyncio.TimeoutError as err:
            raise HeathCheckError(reason="Service is slowing down") from err

        return heath_report
