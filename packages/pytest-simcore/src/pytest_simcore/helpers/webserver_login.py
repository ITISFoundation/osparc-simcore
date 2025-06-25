import contextlib
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, TypedDict

from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.users import UserID
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import users as users_table
from simcore_service_webserver.db.models import UserRole, UserStatus
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.groups import api as groups_service
from simcore_service_webserver.login._constants import MSG_LOGGED_IN
from simcore_service_webserver.login._invitations_service import create_invitation_token
from simcore_service_webserver.products.products_service import list_products
from simcore_service_webserver.security import security_service
from sqlalchemy.ext.asyncio import AsyncEngine
from yarl import URL

from .assert_checks import assert_status
from .faker_factories import DEFAULT_FAKER, DEFAULT_TEST_PASSWORD, random_user
from .postgres_tools import insert_and_get_row_lifespan


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


async def _create_user_in_db(
    sqlalchemy_async_engine: AsyncEngine,
    exit_stack: contextlib.AsyncExitStack,
    data: dict | None = None,
) -> UserInfoDict:

    # create fake
    data = data or {}
    data.setdefault("status", UserStatus.ACTIVE.name)
    data.setdefault("role", UserRole.USER.name)

    raw_password = DEFAULT_TEST_PASSWORD

    # inject in db
    user = await exit_stack.enter_async_context(
        insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
            sqlalchemy_async_engine,
            table=users_table,
            values=random_user(password=raw_password, **data),
            pk_col=users_table.c.id,
        )
    )
    assert "first_name" in user
    assert "last_name" in user

    return UserInfoDict(
        # required
        #  - in db
        id=user["id"],
        name=user["name"],
        email=user["email"],
        primary_gid=user["primary_gid"],
        status=(
            UserStatus(user["status"])
            if not isinstance(user["status"], UserStatus)
            else user["status"]
        ),
        role=(
            UserRole(user["role"])
            if not isinstance(user["role"], UserRole)
            else user["role"]
        ),
        # optional
        #  - in db
        created_at=(
            user["created_at"]
            if isinstance(user["created_at"], datetime)
            else datetime.fromisoformat(user["created_at"])
        ),
        password_hash=user["password_hash"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        phone=user["phone"],
        # extras
        raw_password=raw_password,
    )


async def _register_user_in_default_product(app: web.Application, user_id: UserID):
    products = list_products(app)
    assert products
    product_name = products[0].name

    return await groups_service.auto_add_user_to_product_group(
        app, user_id, product_name=product_name
    )


async def _create_account_in_db(
    app: web.Application,
    exit_stack: contextlib.AsyncExitStack,
    user_data: dict[str, Any] | None = None,
) -> UserInfoDict:
    # users, groups in db
    user = await _create_user_in_db(
        get_asyncpg_engine(app), exit_stack=exit_stack, data=user_data
    )

    # user has default product
    await _register_user_in_default_product(app, user_id=user["id"])
    return user


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


class NewUser:
    def __init__(
        self,
        user_data: dict[str, Any] | None = None,
        app: web.Application | None = None,
    ):
        self.user_data = user_data
        self.user = None

        assert app
        self.app = app

        self.exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> UserInfoDict:
        self.user = await _create_account_in_db(
            self.app, self.exit_stack, self.user_data
        )
        return self.user

    async def __aexit__(self, *args):
        await self.exit_stack.aclose()


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

    async def __aenter__(self) -> "NewInvitation":
        # creates host user
        assert self.client.app
        self.user = await _create_user_in_db(self.client.app, self.user_data)

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
