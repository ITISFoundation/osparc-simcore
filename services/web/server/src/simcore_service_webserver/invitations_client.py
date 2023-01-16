import contextlib
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from aiohttp import BasicAuth, ClientSession, web
from aiohttp.client_exceptions import ClientError
from pydantic import BaseModel, EmailStr, parse_obj_as

from ._constants import APP_SETTINGS_KEY
from .invitations_settings import InvitationsSettings

logger = logging.getLogger(__name__)


class InvitationContent(BaseModel):
    issuer: str
    guest: EmailStr
    trial_account_days: Optional[int] = None
    created: datetime


@dataclass(frozen=True)
class InvitationsServiceApi:
    client: ClientSession
    settings: InvitationsSettings
    exit_stack: contextlib.AsyncExitStack
    healthcheck_path: str = "/"

    @classmethod
    async def create(cls, settings: InvitationsSettings) -> "InvitationsServiceApi":
        exit_stack = contextlib.AsyncExitStack()
        client_session = await exit_stack.enter_async_context(
            ClientSession(
                base_url=settings.base_url,
                auth=BasicAuth(
                    login=settings.INVITATIONS_USERNAME,
                    password=settings.INVITATIONS_PASSWORD.get_secret_value(),
                ),
                raise_for_status=True,
            )
        )
        return cls(client=client_session, exit_stack=exit_stack, settings=settings)

    #
    # common SDK
    #

    async def close(self) -> None:
        await self.exit_stack.aclose()

    async def ping(self) -> bool:
        with suppress(ClientError):
            response = await self.client.get(self.healthcheck_path)
            return response.status == web.HTTPOk.status_code
        return False

    is_responsive = ping

    #
    # service API
    #

    async def extract_invitation(self, invitation_url: str) -> InvitationContent:
        response = await self.client.post(
            url=f"/{self.settings.INVITATIONS_VTAG}/invitations:extract",
            data={"invitation_url": invitation_url},
        )
        invitation = parse_obj_as(InvitationContent, await response.json())
        return invitation


#
# EVENTS
#

_APP_KEY = f"{__name__}.{InvitationsServiceApi.__name__}"


async def invitations_service_api_cleanup_ctx(app: web.Application):

    app[_APP_KEY] = service_api = InvitationsServiceApi.create(
        settings=app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS
    )

    yield

    await service_api.close()


def get_invitations_service_api(app: web.Application) -> InvitationsServiceApi:
    assert app[_APP_KEY]  # nosec
    return app[_APP_KEY]
