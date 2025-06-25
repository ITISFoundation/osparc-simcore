import contextlib
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, TypedDict

from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.users import UserID
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole, UserStatus
from simcore_service_webserver.groups import api as groups_service
from simcore_service_webserver.login._constants import MSG_LOGGED_IN
from simcore_service_webserver.login._invitations_service import create_invitation_token
from simcore_service_webserver.login._login_repository_legacy import (
    AsyncpgStorage,
    get_plugin_storage,
)
from simcore_service_webserver.products.products_service import list_products
from simcore_service_webserver.security import security_service
from yarl import URL

from .assert_checks import assert_status
from .faker_factories import DEFAULT_FAKER, DEFAULT_TEST_PASSWORD, random_user


# WARNING: DO NOT use UserDict is already in https://docs.python.org/3/library/collections.html#collections.UserDictclass UserRowDict(TypedDict):
# NOTE: this is modified dict version of packages/postgres-database/src/simcore_postgres_database/models/users.py for testing purposes
class _UserInfoDictRequired(TypedDict, total=True):
    id: int
    name: str
    email: str
    primary_gid: str
    raw_password: str
    status: UserStatus
    role: UserRole


class UserInfoDict(_UserInfoDictRequired, total=False):
    created_at: datetime
    password_hash: str
    first_name: str
    last_name: str
    phone: str


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


async def _create_user(app: web.Application, data=None) -> UserInfoDict:
    db: AsyncpgStorage = get_plugin_storage(app)

    # create
    data = data or {}
    data.setdefault("status", UserStatus.ACTIVE.name)
    data.setdefault("role", UserRole.USER.name)
    data.setdefault("password", DEFAULT_TEST_PASSWORD)
    user = await db.create_user(random_user(**data))

    # get
    user = await db.get_user({"id": user["id"]})
    assert "first_name" in user
    assert "last_name" in user

    # adds extras
    extras = {"raw_password": data["password"]}

    return UserInfoDict(
        **{
            key: user[key]
            for key in [
                "id",
                "name",
                "email",
                "primary_gid",
                "status",
                "role",
                "created_at",
                "password_hash",
                "first_name",
                "last_name",
                "phone",
            ]
        },
        **extras,
    )


async def _register_user_in_default_product(app: web.Application, user_id: UserID):
    products = list_products(app)
    assert products
    product_name = products[0].name

    return await groups_service.auto_add_user_to_product_group(
        app, user_id, product_name=product_name
    )


async def _create_account(
    app: web.Application,
    user_data: dict[str, Any] | None = None,
) -> UserInfoDict:
    # users, groups in db
    user = await _create_user(app, user_data)
    # user has default product
    await _register_user_in_default_product(app, user_id=user["id"])
    return user


async def log_client_in(
    client: TestClient,
    user_data: dict[str, Any] | None = None,
    *,
    enable_check=True,
) -> UserInfoDict:
    assert client.app

    # create account
    user = await _create_account(client.app, user_data=user_data)

    # login
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


class NewUser:
    def __init__(
        self,
        user_data: dict[str, Any] | None = None,
        app: web.Application | None = None,
    ):
        self.user_data = user_data
        self.user = None
        assert app
        self.db = get_plugin_storage(app)
        self.app = app

    async def __aenter__(self) -> UserInfoDict:
        self.user = await _create_account(self.app, self.user_data)
        return self.user

    async def __aexit__(self, *args):
        await self.db.delete_user(self.user)


class LoggedUser(NewUser):
    def __init__(self, client: TestClient, user_data=None, *, check_if_succeeds=True):
        super().__init__(user_data, client.app)
        self.client = client
        self.enable_check = check_if_succeeds
        assert self.client.app

    async def __aenter__(self) -> UserInfoDict:
        self.user = await log_client_in(
            self.client, self.user_data, enable_check=self.enable_check
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

    async def __aenter__(self) -> "NewInvitation":
        # creates host user
        assert self.client.app
        self.user = await _create_user(self.client.app, self.user_data)

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
