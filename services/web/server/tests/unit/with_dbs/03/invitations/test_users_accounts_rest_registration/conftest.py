# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, TypedDict
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole, UserStatus
from faker import Faker
from models_library.api_schemas_webserver.auth import AccountRequestInfo
from models_library.groups import AccessRightsDict
from models_library.notifications import Channel
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import DEFAULT_TEST_PASSWORD
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_users import NewUser
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.login import _auth_service
from simcore_service_webserver.models import PhoneNumberStr
from simcore_service_webserver.notifications._models import TemplatePreview, TemplateRef


class SeededUserAccountsEmails(TypedDict):
    pending_registered: str
    pending_unregistered: str
    reviewed_registered: str
    reviewed_unregistered: str


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    # disables GC and DB-listener
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
        },
    )


@pytest.fixture
def mock_notifications_send_message(mocker: MockerFixture) -> AsyncMock:
    """Mock the notifications_service.send_message to avoid RabbitMQ dependency."""
    return mocker.patch(
        "simcore_service_webserver.notifications.notifications_service.send_message",
        return_value=AsyncMock(),
    )


@pytest.fixture
async def support_user(
    support_group_before_app_starts: dict,
    client: TestClient,
) -> AsyncIterator[UserInfoDict]:
    """Creates an active user that belongs to the product's support group."""
    async with NewUser(
        user_data={
            "name": "support-user",
            "status": UserStatus.ACTIVE.name,
            "role": UserRole.USER.name,
        },
        app=client.app,
    ) as user_info:
        # Add the user to the support group
        assert client.app

        from simcore_service_webserver.groups import _groups_repository  # noqa: PLC0415

        # Now add user to support group with read-only access
        await _groups_repository.add_new_user_in_group(
            client.app,
            group_id=support_group_before_app_starts["gid"],
            new_user_id=user_info["id"],
            access_rights=AccessRightsDict(read=True, write=False, delete=False),
        )

        yield user_info


@pytest.fixture
def account_request_form(
    faker: Faker,
    user_phone_number: PhoneNumberStr,
) -> dict[str, Any]:
    # This is AccountRequestInfo.form
    form = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": faker.email(),
        "phone": user_phone_number,
        "company": faker.company(),
        # billing info
        "address": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "postalCode": faker.postcode(),
        "country": faker.country(),
        # extras
        "application": faker.word(),
        "description": faker.sentence(),
        "hear": faker.word(),
        "privacyPolicy": True,
        "eula": True,
    }

    # keeps in sync fields from example and this fixture
    assert set(form) == set(AccountRequestInfo.model_json_schema()["example"]["form"])
    return form


@pytest.fixture
async def pre_registration_details_db_cleanup(
    client: TestClient,
) -> AsyncGenerator[None]:
    """Fixture to clean up pre-registration details AND orphan users created during tests."""

    assert client.app
    engine = get_asyncpg_engine(client.app)

    # Snapshot user IDs before the test body runs
    async with engine.connect() as conn:
        result = await conn.execute(sa.select(users.c.id))
        user_ids_before = {row.id for row in result}

    yield

    # Tear down
    async with engine.connect() as conn:
        # 1. Clean pre-registration details
        await conn.execute(sa.delete(users_pre_registration_details))

        # 2. Remove users created during the test body (orphans from create_user / new_user calls)
        result = await conn.execute(sa.select(users.c.id))
        user_ids_after = {row.id for row in result}
        orphan_ids = user_ids_after - user_ids_before
        if orphan_ids:
            await conn.execute(sa.delete(users).where(users.c.id.in_(orphan_ids)))

        await conn.commit()


@pytest.fixture
async def seeded_user_accounts_for_registered_review_filters(
    client: TestClient,
    account_request_form: dict[str, Any],
    faker: Faker,
    product_name: ProductName,
    mock_invitations_service_http_api: AioResponsesMock,
    mock_notifications_preview_template: AsyncMock,
) -> SeededUserAccountsEmails:
    assert client.app

    async def _pre_register(email: str) -> None:
        form_data = account_request_form.copy()
        form_data["firstName"] = faker.first_name()
        form_data["lastName"] = faker.last_name()
        form_data["email"] = email

        resp = await client.post(
            "/v0/admin/user-accounts:pre-register",
            json=form_data,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        )
        await assert_status(resp, status.HTTP_200_OK)

    async def _approve(email: str) -> None:
        preview_url = client.app.router["preview_approval_user_account"].url_for()
        resp = await client.post(
            f"{preview_url}",
            headers={X_PRODUCT_NAME_HEADER: product_name},
            json={
                "email": email,
                "invitation": {"trialAccountDays": 7},
            },
        )
        preview_data, _ = await assert_status(resp, status.HTTP_200_OK)

        approve_url = client.app.router["approve_user_account"].url_for()
        resp = await client.post(
            f"{approve_url}",
            headers={X_PRODUCT_NAME_HEADER: product_name},
            json={"email": email, "invitationUrl": preview_data["invitationUrl"]},
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    async def _reject(email: str) -> None:
        reject_url = client.app.router["reject_user_account"].url_for()
        resp = await client.post(
            f"{reject_url}",
            headers={X_PRODUCT_NAME_HEADER: product_name},
            json={"email": email},
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # pending + unregistered
    pending_unregistered_email = faker.email()
    await _pre_register(pending_unregistered_email)

    # pending + registered (anomaly): pre-register first, then create the user
    pending_registered_email = faker.email()
    await _pre_register(pending_registered_email)
    await _auth_service.create_user(
        client.app,
        email=pending_registered_email,
        password=DEFAULT_TEST_PASSWORD,
        status_upon_creation=UserStatus.ACTIVE,
        expires_at=None,
    )

    # reviewed + unregistered
    reviewed_unregistered_email = faker.email()
    await _pre_register(reviewed_unregistered_email)
    await _reject(reviewed_unregistered_email)

    # reviewed + registered
    reviewed_registered_email = faker.email()
    await _pre_register(reviewed_registered_email)
    await _approve(reviewed_registered_email)
    await _auth_service.create_user(
        client.app,
        email=reviewed_registered_email,
        password=DEFAULT_TEST_PASSWORD,
        status_upon_creation=UserStatus.ACTIVE,
        expires_at=None,
    )

    return {
        "pending_registered": pending_registered_email,
        "pending_unregistered": pending_unregistered_email,
        "reviewed_registered": reviewed_registered_email,
        "reviewed_unregistered": reviewed_unregistered_email,
    }


@pytest.fixture
def mock_notifications_preview_template(mocker: MockerFixture) -> AsyncMock:
    """Mock the notifications_service.preview_template to avoid RabbitMQ dependency."""

    async def _fake_preview_template(
        app,
        *,
        product_name,
        ref,
        context,
    ) -> TemplatePreview:
        first_name = context.get("user", {}).get("first_name", "User")
        if ref.template_name == "account_approved":
            invitation_url = context.get("link", "https://example.com")
            trial_days = context.get("trial_account_days")
            extra_credits = context.get("extra_credits")
            body_parts = [f"<p>Dear {first_name},</p>", "<p>Your account has been approved!</p>"]
            if trial_days:
                body_parts.append(f"<p>Trial period: {trial_days} days</p>")
            if extra_credits:
                body_parts.append(f"<p>Extra credits: ${extra_credits}</p>")
            body_parts.append(f'<p><a href="{invitation_url}">Accept Invitation</a></p>')
            return TemplatePreview(
                ref=TemplateRef(channel=Channel.email, template_name="account_approved"),
                message_content={
                    "subject": "Your account request has been accepted",
                    "body_html": "\n".join(body_parts),
                    "body_text": f"Dear {first_name}, your account has been approved.",
                },
            )
        if ref.template_name == "account_rejected":
            return TemplatePreview(
                ref=TemplateRef(channel=Channel.email, template_name="account_rejected"),
                message_content={
                    "subject": "Your account request has been denied",
                    "body_html": (
                        f"<p>Dear {first_name},</p>"
                        "<p>We regret to inform you that your account request has been denied.</p>"
                    ),
                    "body_text": f"Dear {first_name}, your account request has been denied.",
                },
            )
        msg = f"Unexpected template_name={ref.template_name}"
        raise ValueError(msg)

    return mocker.patch(
        "simcore_service_webserver.notifications.notifications_service.preview_template",
        side_effect=_fake_preview_template,
    )
