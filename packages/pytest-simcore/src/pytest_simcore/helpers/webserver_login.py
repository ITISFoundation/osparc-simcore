import contextlib
import re
from collections.abc import AsyncIterator
from typing import Any

from aiohttp.test_utils import TestClient
from servicelib.aiohttp import status
from simcore_service_webserver.login._invitations_service import create_invitation_token
from simcore_service_webserver.login._login_repository_legacy import (
    get_plugin_storage,
)
from simcore_service_webserver.login.constants import MSG_LOGGED_IN
from simcore_service_webserver.security import security_service
from yarl import URL

from .assert_checks import assert_status
from .faker_factories import DEFAULT_FAKER
from .webserver_users import NewUser, UserInfoDict, _create_account_in_db

TEST_MARKS = re.compile(r"TEST (\w+):(.*)")


def parse_test_marks(text):
    """Checs for marks as

    TEST name:123123
    TEST link:some-value
    """
    marks = {}
    for m in TEST_MARKS.finditer(text):
        key, value = m.groups()
        marks[key] = value.strip()
    return marks


def parse_link(text):
    link = parse_test_marks(text)["link"]
    return URL(link).path


async def log_client_in(
    client: TestClient,
    user_data: dict[str, Any] | None = None,
    *,
    exit_stack: contextlib.AsyncExitStack,
    enable_check: bool = True,
) -> UserInfoDict:
    assert client.app

    # create account
    user = await _create_account_in_db(
        client.app, exit_stack=exit_stack, user_data=user_data
    )

    # login (requires)
    url = client.app.router["auth_login"].url_for()
    reponse = await client.post(
        str(url),
        json={
            "email": user["email"],
            "password": user["raw_password"],
        },
    )

    if enable_check:
        await assert_status(reponse, status.HTTP_200_OK, MSG_LOGGED_IN)

    return user


class LoggedUser(NewUser):
    def __init__(self, client: TestClient, user_data=None, *, check_if_succeeds=True):
        super().__init__(user_data, client.app)
        self.client = client
        self.enable_check = check_if_succeeds
        assert self.client.app

    async def __aenter__(self) -> UserInfoDict:
        self.user = await log_client_in(
            self.client,
            self.user_data,
            exit_stack=self.exit_stack,
            enable_check=self.enable_check,
        )
        return self.user

    async def __aexit__(self, *args):
        assert self.client.app
        # NOTE: cache key is based on an email. If the email is
        # reused during the test, then it creates quite some noise
        await security_service.clean_auth_policy_cache(self.client.app)
        return await super().__aexit__(*args)


@contextlib.asynccontextmanager
async def switch_client_session_to(
    client: TestClient, user: UserInfoDict
) -> AsyncIterator[TestClient]:
    assert client.app

    await client.post(f'{client.app.router["auth_logout"].url_for()}')
    # sometimes 4xx if user already logged out. Ignore

    resp = await client.post(
        f'{client.app.router["auth_login"].url_for()}',
        json={
            "email": user["email"],
            "password": user["raw_password"],
        },
    )
    await assert_status(resp, status.HTTP_200_OK)

    yield client

    resp = await client.post(f'{client.app.router["auth_logout"].url_for()}')
    await assert_status(resp, status.HTTP_200_OK)


class NewInvitation(NewUser):
    def __init__(
        self,
        client: TestClient,
        guest_email: str | None = None,
        host: dict | None = None,
        trial_days: int | None = None,
        extra_credits_in_usd: int | None = None,
    ):
        assert client.app
        super().__init__(user_data=host, app=client.app)
        self.client = client
        self.tag = f"Created by {guest_email or DEFAULT_FAKER.email()}"
        self.confirmation = None
        self.trial_days = trial_days
        self.extra_credits_in_usd = extra_credits_in_usd
        self.db = get_plugin_storage(self.app)

    async def __aenter__(self) -> "NewInvitation":
        # creates host user
        assert self.client.app
        self.user = await super().__aenter__()

        self.confirmation = await create_invitation_token(
            self.db,
            user_id=self.user["id"],
            user_email=self.user["email"],
            tag=self.tag,
            trial_days=self.trial_days,
            extra_credits_in_usd=self.extra_credits_in_usd,
        )
        return self

    async def __aexit__(self, *args):
        if await self.db.get_confirmation(self.confirmation):
            await self.db.delete_confirmation(self.confirmation)
