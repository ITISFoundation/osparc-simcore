import re
from datetime import datetime
from typing import TypedDict

from aiohttp import web
from aiohttp.test_utils import TestClient
from simcore_service_webserver.db.models import UserRole, UserStatus
from simcore_service_webserver.login._constants import MSG_LOGGED_IN
from simcore_service_webserver.login._registration import create_invitation_token
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage
from yarl import URL

from .rawdata_fakers import FAKE, random_user
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
    created_ip: int
    password_hash: str


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


async def create_fake_user(db: AsyncpgStorage, data=None) -> UserInfoDict:
    """Creates a fake user and inserts it in the users table in the database"""
    data = data or {}
    data.setdefault("password", "secret")
    data.setdefault("status", UserStatus.ACTIVE.name)
    data.setdefault("role", UserRole.USER.name)
    params = random_user(**data)

    user = await db.create_user(params)
    user["raw_password"] = data["password"]
    return user


async def log_client_in(
    client: TestClient, user_data=None, *, enable_check=True
) -> UserInfoDict:
    # creates user directly in db
    assert client.app
    db: AsyncpgStorage = get_plugin_storage(client.app)

    user = await create_fake_user(db, user_data)

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
    def __init__(self, params=None, app: web.Application | None = None):
        self.params = params
        self.user = None
        assert app
        self.db = get_plugin_storage(app)

    async def __aenter__(self) -> UserInfoDict:
        self.user = await create_fake_user(self.db, self.params)
        return self.user

    async def __aexit__(self, *args):
        await self.db.delete_user(self.user)


class LoggedUser(NewUser):
    def __init__(self, client, params=None, *, check_if_succeeds=True):
        super().__init__(params, client.app)
        self.client = client
        self.enable_check = check_if_succeeds

    async def __aenter__(self) -> UserInfoDict:
        self.user = await log_client_in(
            self.client, self.params, enable_check=self.enable_check
        )
        return self.user


class NewInvitation(NewUser):
    def __init__(
        self,
        client: TestClient,
        guest_email: str | None = None,
        host: dict | None = None,
        trial_days: int | None = None,
    ):
        assert client.app
        super().__init__(params=host, app=client.app)
        self.client = client
        self.tag = f"Created by {guest_email or FAKE.email()}"
        self.confirmation = None
        self.trial_days = trial_days

    async def __aenter__(self) -> "NewInvitation":
        # creates host user
        assert self.client.app
        db: AsyncpgStorage = get_plugin_storage(self.client.app)
        self.user = await create_fake_user(db, self.params)

        self.confirmation = await create_invitation_token(
            self.db,
            user_id=self.user["id"],
            user_email=self.user["email"],
            tag=self.tag,
            trial_days=self.trial_days,
        )
        return self

    async def __aexit__(self, *args):
        if await self.db.get_confirmation(self.confirmation):
            await self.db.delete_confirmation(self.confirmation)
