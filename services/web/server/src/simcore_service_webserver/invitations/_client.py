import contextlib
import logging
from dataclasses import dataclass

from aiohttp import BasicAuth, ClientSession, web
from aiohttp.client_exceptions import ClientError
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationContentAndLink,
    ApiInvitationInputs,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyHttpUrl
from yarl import URL

from .._constants import APP_SETTINGS_KEY
from .settings import InvitationsSettings

_logger = logging.getLogger(__name__)


#
# CLIENT
#


@dataclass(frozen=True)
class InvitationsServiceApi:
    client: ClientSession
    settings: InvitationsSettings
    _exit_stack: contextlib.AsyncExitStack
    healthcheck_path: str = "/"

    @classmethod
    async def create(cls, settings: InvitationsSettings) -> "InvitationsServiceApi":
        exit_stack = contextlib.AsyncExitStack()
        client_session = await exit_stack.enter_async_context(
            ClientSession(
                auth=BasicAuth(
                    login=settings.INVITATIONS_USERNAME,
                    password=settings.INVITATIONS_PASSWORD.get_secret_value(),
                ),
                raise_for_status=True,
            )
        )
        return cls(client=client_session, _exit_stack=exit_stack, settings=settings)

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
        await self._exit_stack.aclose()

    async def ping(self) -> bool:
        ok = False
        try:
            response = await self.client.get(self._url(self.healthcheck_path))
            ok = response.ok
        except ClientError as err:
            _logger.debug("Invitations service is not responsive: %s", err)
        return ok

    is_responsive = ping

    #
    # service API
    #

    async def extract_invitation(
        self, invitation_url: AnyHttpUrl
    ) -> ApiInvitationContent:
        response = await self.client.post(
            url=self._url_vtag("/invitations:extract"),
            json={"invitation_url": f"{invitation_url}"},
        )
        return ApiInvitationContent.model_validate(await response.json())

    async def generate_invitation(
        self, params: ApiInvitationInputs
    ) -> ApiInvitationContentAndLink:
        response = await self.client.post(
            url=self._url_vtag("/invitations"),
            json=jsonable_encoder(params),
        )
        return ApiInvitationContentAndLink.model_validate(await response.json())


#
# EVENTS
#

_APP_INVITATIONS_SERVICE_API_KEY = f"{__name__}.{InvitationsServiceApi.__name__}"


async def invitations_service_api_cleanup_ctx(app: web.Application):
    service_api = await InvitationsServiceApi.create(
        settings=app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS
    )

    app[_APP_INVITATIONS_SERVICE_API_KEY] = service_api

    yield

    try:
        await service_api.close()
    except Exception:  # pylint: disable=broad-except
        _logger.warning("Ignoring error while closing service-api")


def get_invitations_service_api(app: web.Application) -> InvitationsServiceApi:
    assert app[_APP_INVITATIONS_SERVICE_API_KEY]  # nosec
    service_api: InvitationsServiceApi = app[_APP_INVITATIONS_SERVICE_API_KEY]
    return service_api
