import re
from datetime import datetime
from typing import Any, TypedDict

from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from simcore_service_webserver.db.models import UserRole, UserStatus
from simcore_service_webserver.groups.api import auto_add_user_to_product_group
from simcore_service_webserver.login._constants import MSG_LOGGED_IN
from simcore_service_webserver.login._registration import create_invitation_token
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage
from simcore_service_webserver.products.api import list_products
from simcore_service_webserver.security.api import clean_auth_policy_cache
from yarl import URL

from .rawdata_fakers import DEFAULT_FAKER, random_user
from .utils_assert import assert_status


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


async def _insert_fake_user(db: AsyncpgStorage, data=None) -> UserInfoDict:
    """Creates a fake user and inserts it in the users table in the database"""
    data = data or {}
    data.setdefault("status", UserStatus.ACTIVE.name)
    data.setdefault("role", UserRole.USER.name)
    params = random_user(**data)

    user = await db.create_user(params)
    user["raw_password"] = data["password"]
    user.setdefault("first_name", None)
    user.setdefault("last_name", None)
    return user


async def _register_user_in_product(
    app: web.Application, user_id: UserID, product_name: ProductName | None = None
) -> GroupID:
    if product_name is None:
        products = list_products(app)
        assert products
        product_name = products[0].name  # TODO: default?

    return await auto_add_user_to_product_group(app, user_id, product_name=product_name)


async def log_client_in(
    client: TestClient,
    user_data=None,
    *,
    enable_check=True,
    product_name: ProductName | None = None,
) -> UserInfoDict:
    # creates user directly in db
    assert client.app
    db: AsyncpgStorage = get_plugin_storage(client.app)

    user = await _insert_fake_user(db, user_data)
    await _register_user_in_product(
        client.app, user_id=user["id"], product_name=product_name
    )

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
        await assert_status(reponse, web.HTTPOk, MSG_LOGGED_IN)

    return user


class NewUser:
    def __init__(
        self, params: dict[str, Any] | None = None, app: web.Application | None = None
    ):
        self.params = params
        self.user = None
        assert app
        self.db = get_plugin_storage(app)
        self.app = app

    async def __aenter__(self) -> UserInfoDict:
        self.user = await _insert_fake_user(self.db, self.params)

        await _register_user_in_product(
            self.app,
            user_id=self.user["id"],
            product_name=self.params.get("product_name", None),
        )

        return self.user

    async def __aexit__(self, *args):
        await self.db.delete_user(self.user)


class LoggedUser(NewUser):
    def __init__(self, client: TestClient, params=None, *, check_if_succeeds=True):
        super().__init__(params, client.app)
        self.client = client
        self.enable_check = check_if_succeeds

    async def __aenter__(self) -> UserInfoDict:
        self.user = await log_client_in(
            self.client, self.params, enable_check=self.enable_check
        )
        return self.user

    async def __aexit__(self, *args):
        # NOTE: cache key is based on an email. If the email is
        # reused during the test, then it creates quite some noise
        await clean_auth_policy_cache(self.client.app)
        return await super().__aexit__(*args)


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
        super().__init__(params=host, app=client.app)
        self.client = client
        self.tag = f"Created by {guest_email or DEFAULT_FAKER.email()}"
        self.confirmation = None
        self.trial_days = trial_days
        self.extra_credits_in_usd = extra_credits_in_usd

    async def __aenter__(self) -> "NewInvitation":
        # creates host user
        assert self.client.app
        db: AsyncpgStorage = get_plugin_storage(self.client.app)
        self.user = await _insert_fake_user(db, self.params)

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
