import contextlib
import logging
from dataclasses import dataclass

from aiohttp import BasicAuth, ClientSession, web
from aiohttp.client_exceptions import ClientError
from yarl import URL

from .._constants import APP_SETTINGS_KEY
from .settings import PaymentsSettings

_logger = logging.getLogger(__name__)


#
# CLIENT
#


@dataclass(frozen=True)
class PaymentsServiceApi:
    client: ClientSession
    settings: PaymentsSettings
    exit_stack: contextlib.AsyncExitStack
    healthcheck_path: str = "/"

    @classmethod
    async def create(cls, settings: PaymentsSettings) -> "PaymentsServiceApi":
        exit_stack = contextlib.AsyncExitStack()
        client_session = await exit_stack.enter_async_context(
            ClientSession(
                auth=BasicAuth(
                    login=settings.PAYMENTS_USERNAME,
                    password=settings.PAYMENTS_PASSWORD.get_secret_value(),
                ),
                raise_for_status=True,
            )
        )
        return cls(client=client_session, exit_stack=exit_stack, settings=settings)

    #
    # common SDK
    #

    def _url(self, rel_url: str):
        return URL(self.settings.base_url) / rel_url.lstrip("/")

    def _url_vtag(self, rel_url: str):
        return URL(self.settings.api_base_url) / rel_url.lstrip("/")

    # NOTE: the functions above are added due to limitations in
    # aioresponses https://github.com/pnuckowski/aioresponses/issues/230
    # we will avoid using ClientSession(base_url=settings.base_url, ... ) and
    # use insteald self._url("/v0/foo")

    async def close(self) -> None:
        """Releases underlying connector from ClientSession [client]"""
        await self.exit_stack.aclose()

    async def is_healthy(self) -> bool:
        try:
            response = await self.client.get(self._url(self.healthcheck_path))
            return response.ok
        except ClientError as err:
            _logger.debug("Payments service is not healty: %s", err)
            return False


#
# EVENTS
#

_APP_PAYMENTS_SERVICE_API_KEY = f"{__name__}.{PaymentsServiceApi.__name__}"


async def payments_service_api_cleanup_ctx(app: web.Application):

    service_api = await PaymentsServiceApi.create(
        settings=app[APP_SETTINGS_KEY].WEBSERVER_PAYMENTS
    )

    app[_APP_PAYMENTS_SERVICE_API_KEY] = service_api

    yield

    try:
        await service_api.close()
    except Exception:  # pylint: disable=broad-except
        _logger.warning("Ignored error while cleaning", exc_info=True)


def get_payments_service_api(app: web.Application) -> PaymentsServiceApi:
    assert app[_APP_PAYMENTS_SERVICE_API_KEY]  # nosec
    service_api: PaymentsServiceApi = app[_APP_PAYMENTS_SERVICE_API_KEY]
    return service_api
