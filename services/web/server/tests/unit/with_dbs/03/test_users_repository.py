# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections.abc import AsyncIterable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestServer
from faker import Faker
from models_library.api_schemas_webserver.users import UserForAdminGet
from models_library.products import ProductName
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import get_asyncpg_engine, setup_db
from simcore_service_webserver.users import _users_service
from simcore_service_webserver.users._users_repository import (
    create_user_pre_registration,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def web_server(
    event_loop: asyncio.AbstractEventLoop,
    app_environment: EnvVarsDict,  # configs
    postgres_db: sa.engine.Engine,  # db-ready
    webserver_test_server_port: int,
    aiohttp_server: Callable,
) -> TestServer:
    """Creates an app that setups the database only"""
    app = web.Application()

    app = create_safe_application()
    setup_settings(app)
    setup_db(app)

    return event_loop.run_until_complete(
        aiohttp_server(app, port=webserver_test_server_port)
    )


@pytest.fixture
def app(web_server: TestServer) -> web.Application:
    """Setup and started app with db"""
    _app = web_server.app
    assert get_asyncpg_engine(_app)
    return _app


@pytest.fixture
def asyncpg_engine(
    app: web.Application,
) -> AsyncEngine:
    """Returns the asyncpg engine ready to be used against postgres"""
    return get_asyncpg_engine(app)


@pytest.fixture
async def product_owner_user(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    """A PO user in the database"""

    from pytest_simcore.helpers.faker_factories import (
        random_user,
    )
    from pytest_simcore.helpers.postgres_tools import (
        insert_and_get_row_lifespan,
    )
    from simcore_postgres_database.models.users import UserRole, users

    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        table=users,
        values=random_user(
            faker,
            email="po-user@email.com",
            name="po-user-fixture",
            role=UserRole.PRODUCT_OWNER,
        ),
        pk_col=users.c.id,
    ) as row:
        yield row


async def test_create_user_pre_registration(
    app: web.Application, product_name: ProductName, product_owner_user: dict[str, Any]
):
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)

    test_email = "test.user@example.com"
    created_by_user_id = product_owner_user["id"]
    institution = "Test Institution"
    other_values: dict[str, Any] = {
        "institution": institution,
        "pre_first_name": "Test",
        "pre_last_name": "User",
    }

    # Act
    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email=test_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **other_values,
    )

    # Assert
    async with asyncpg_engine.connect() as conn:
        # Query to check if the record was inserted
        result = await conn.execute(
            sa.select(users_pre_registration_details).where(
                (users_pre_registration_details.c.pre_email == test_email)
                & (users_pre_registration_details.c.product_name == product_name)
            )
        )
        record = result.first()

        # Clean up - delete the test record
        await conn.execute(
            sa.delete(users_pre_registration_details).where(
                users_pre_registration_details.c.id == pre_registration_id
            )
        )
        await conn.commit()

    # Verify the record was created with correct values
    assert record is not None
    assert record.pre_email == test_email
    assert record.created_by == created_by_user_id
    assert record.product_name == product_name
    assert record.institution == institution


async def test_search_users_as_admin_real_user(
    app: web.Application, product_name: ProductName, product_owner_user: dict[str, Any]
):
    """Test searching for a real user as admin"""
    # Arrange
    user_email = product_owner_user["email"]

    # Act
    found_users = await _users_service.search_users_as_admin(
        app, email_glob=user_email, product_name=product_name, include_products=False
    )

    # Assert
    assert len(found_users) == 1
    found_user = found_users[0]
    assert found_user.email == user_email
    assert found_user.registered is True
    assert (
        found_user.products is None
    )  # This test user does not have a product associated with it

    # Verify the UserForAdminGet model is populated correctly
    assert isinstance(found_user, UserForAdminGet)
    # If first_name is populated in the fixture, it should be in the result
    if product_owner_user.get("first_name"):
        assert found_user.first_name == product_owner_user["first_name"]


async def test_search_users_as_admin_pre_registered_user(
    app: web.Application, product_name: ProductName, product_owner_user: dict[str, Any]
):
    """Test searching for a pre-registered user as admin"""
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)
    pre_registered_email = "pre-registered@example.com"
    created_by_user_id = product_owner_user["id"]

    pre_registration_details = {
        "pre_first_name": "Pre-Registered",
        "pre_last_name": "User",
        "institution": "Test University",
        "address": "123 Test Street",
        "city": "Test City",
        "state": "Test State",
        "postal_code": "12345",
        "country": "US",
    }

    # Create a pre-registered user
    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email=pre_registered_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )

    try:
        # Act
        found_users = await _users_service.search_users_as_admin(
            app, email_glob=pre_registered_email, product_name=product_name
        )

        # Assert
        assert len(found_users) == 1
        pre_registered_user = found_users[0]
        assert pre_registered_user.email == pre_registered_email
        assert (
            pre_registered_user.registered is False
        )  # Pre-registered users are not yet registered
        assert (
            pre_registered_user.institution == pre_registration_details["institution"]
        )
        assert (
            pre_registered_user.first_name == pre_registration_details["pre_first_name"]
        )
        assert (
            pre_registered_user.last_name == pre_registration_details["pre_last_name"]
        )
        assert pre_registered_user.address == pre_registration_details["address"]

        # Verify the invited_by field is populated (should be the name of the product owner)
        assert pre_registered_user.invited_by is not None

    finally:
        # Clean up - delete the test record
        async with asyncpg_engine.connect() as conn:
            await conn.execute(
                sa.delete(users_pre_registration_details).where(
                    users_pre_registration_details.c.id == pre_registration_id
                )
            )
            await conn.commit()


async def test_search_users_as_admin_wildcard(
    app: web.Application, product_name: ProductName, product_owner_user: dict[str, Any]
):
    """Test searching for users with wildcards"""
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)
    email_domain = "@example.com"

    # Create multiple pre-registered users with the same domain
    emails = [f"user1{email_domain}", f"user2{email_domain}", f"different@other.com"]
    created_by_user_id = product_owner_user["id"]

    try:
        # Create pre-registered users
        for email in emails:
            await create_user_pre_registration(
                asyncpg_engine,
                email=email,
                created_by=created_by_user_id,
                product_name=product_name,
                institution="Test Institution",
            )

        # Act - search with wildcard for the domain
        found_users = await _users_service.search_users_as_admin(
            app, email_glob=f"*{email_domain}", product_name=product_name
        )

        # Assert
        assert len(found_users) == 2  # Should find the two users with @example.com
        emails_found = [user.email for user in found_users]
        assert f"user1{email_domain}" in emails_found
        assert f"user2{email_domain}" in emails_found
        assert "different@other.com" not in emails_found

    finally:
        # Clean up - delete all test records
        async with asyncpg_engine.connect() as conn:
            for email in emails:
                await conn.execute(
                    sa.delete(users_pre_registration_details).where(
                        (users_pre_registration_details.c.pre_email == email)
                        & (
                            users_pre_registration_details.c.product_name
                            == product_name
                        )
                    )
                )
            await conn.commit()
