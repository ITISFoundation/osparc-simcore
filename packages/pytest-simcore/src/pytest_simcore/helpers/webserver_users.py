import contextlib
from datetime import datetime
from typing import Any, TypedDict

from aiohttp import web
from common_library.users_enums import UserRole, UserStatus
from models_library.users import UserID
from simcore_postgres_database.models.users import users as users_table
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.groups import api as groups_service
from simcore_service_webserver.products.products_service import list_products
from sqlalchemy.ext.asyncio import AsyncEngine

from .faker_factories import DEFAULT_TEST_PASSWORD, random_user
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


async def _create_user_in_db(
    sqlalchemy_async_engine: AsyncEngine,
    exit_stack: contextlib.AsyncExitStack,
    data: dict | None = None,
) -> UserInfoDict:

    # create fake
    data = data or {}
    data.setdefault("status", UserStatus.ACTIVE.name)
    data.setdefault("role", UserRole.USER.name)
    data.setdefault("password", DEFAULT_TEST_PASSWORD)

    raw_password = data["password"]

    # inject in db
    user = await exit_stack.enter_async_context(
        insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
            sqlalchemy_async_engine,
            table=users_table,
            values=random_user(**data),
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
