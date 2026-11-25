# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

"""SEC-WS-31: /auth/register must not grant a session from a password check
alone on 2FA-required products, and DB invitation codes must stay bound to the
email/product they were issued for.
"""

from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewInvitation, NewUser
from pytest_simcore.helpers.webserver_users import DEFAULT_TEST_PASSWORD, UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.models import (
    GroupType,
    UserStatus,
    confirmations,
    groups,
    products,
    user_to_groups,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.login import _auth_service, _invitations_service
from simcore_service_webserver.login._controller.rest._rest_dependencies import (
    get_confirmation_service,
)
from simcore_service_webserver.login.constants import CODE_PHONE_NUMBER_REQUIRED

pytest_simcore_core_services_selection = ["postgres", "redis", "rabbit"]
pytest_simcore_ops_services_selection = []

pytestmark = pytest.mark.usefixtures("clean_2fa_redis_state")


@pytest.fixture
def mocked_twilio_service(mocker: MockerFixture) -> dict[str, MockType]:
    """Mocks SMS delivery in registration and login modules"""
    mock = mocker.patch(
        "simcore_service_webserver.login._controller.rest.registration._twofa_service.send_sms_code",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.login._controller.rest.auth._twofa_service.send_sms_code",
        new=mock,
    )
    return {"send_sms_code_for_registration": mock}


@pytest.fixture
def postgres_db(postgres_db_with_2fa_enabled_for_osparc: sa.engine.Engine) -> sa.engine.Engine:
    """'osparc' product with LOGIN_2FA_REQUIRED + twilio sid"""
    return postgres_db_with_2fa_enabled_for_osparc


@pytest.fixture
async def victim_outside_product(
    client: TestClient,
    user_email: str,
) -> AsyncIterator[UserInfoDict]:
    """Existing ACTIVE account that is NOT a member of the default product:
    the state where /auth/register reaches the existing-user branch
    """
    assert client.app
    async with NewUser(
        user_data={"email": user_email, "status": UserStatus.ACTIVE.name},
        app=client.app,
    ) as user:
        # NewUser auto-joins the default product: remove that membership (and
        # commit it) so that registration in the default product reaches the
        # existing-user branch instead of raising 409
        async with get_asyncpg_engine(client.app).begin() as conn:
            product_group_ids = (
                (await conn.execute(sa.select(products.c.group_id).where(products.c.group_id.is_not(None))))
                .scalars()
                .all()
            )
            await conn.execute(
                user_to_groups.delete().where(
                    (user_to_groups.c.uid == user["id"]) & (user_to_groups.c.gid.in_(product_group_ids))
                )
            )
        try:
            yield user
        finally:
            # rows referencing the user (directly or via its personal group)
            # must go before the user teardown in NewUser.__aexit__:
            # - invitation confirmations (FK to users)
            # - wallets, created by the product-access grant, whose gid is
            #   RESTRICTed to the user's owner group
            async with get_asyncpg_engine(client.app).begin() as conn:
                primary_gid = (
                    sa.select(user_to_groups.c.gid)
                    .select_from(sa.join(groups, user_to_groups, user_to_groups.c.gid == groups.c.gid))
                    .where((user_to_groups.c.uid == user["id"]) & (groups.c.type == GroupType.PRIMARY))
                )
                await conn.execute(wallets.delete().where(wallets.c.owner.in_(primary_gid)))
                await conn.execute(confirmations.delete().where(confirmations.c.user_id == user["id"]))


async def _create_invitation_code(
    client: TestClient,
    issuer: UserInfoDict,
    *,
    guest_email: str | None = None,
    product: ProductName | None = None,
) -> str:
    assert client.app
    data = _invitations_service.ConfirmedInvitationData(
        issuer="ops@example.com",
        guest=guest_email,
        trial_account_days=None,
        product=product,
    )
    confirmation = await get_confirmation_service(client.app).create_confirmation(
        user_id=UserID(issuer["id"]),
        action=_invitations_service.ConfirmationAction.INVITATION.name,
        data=data.model_dump_json(),
    )
    return confirmation.code


async def test_register_existing_user_password_alone_gets_no_session(
    client: TestClient,
    victim_outside_product: UserInfoDict,
):
    """Wrong password through /auth/register is a failed login, never a
    session grant on the victim's account
    """
    assert client.app
    code = await _create_invitation_code(client, victim_outside_product)

    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": victim_outside_product["email"],
            "password": "wrong-password-9f3k",
            "invitation": code,
        },
    )
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)


async def test_register_existing_user_continues_with_second_factor(
    client: TestClient,
    user_phone_number: str,
    victim_outside_product: UserInfoDict,
    mocked_twilio_service: dict[str, MockType],
    mocked_notifications_service_send_message_from_template,
):
    assert client.app
    assert victim_outside_product["raw_password"] == DEFAULT_TEST_PASSWORD
    code = await _create_invitation_code(client, victim_outside_product)

    # 1. password check -> second factor required, no identity granted
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": victim_outside_product["email"],
            "password": DEFAULT_TEST_PASSWORD,
            "invitation": code,
        },
    )
    data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)
    assert data["name"] == CODE_PHONE_NUMBER_REQUIRED

    # the half-open session has no identity: a login-required route rejects it
    logout_url = client.app.router["auth_logout"].url_for()
    response = await client.post(logout_url.path, json={})
    assert response.status == status.HTTP_401_UNAUTHORIZED

    # a bogus 2FA code must not complete the login
    url = client.app.router["auth_login_2fa"].url_for()
    response = await client.post(
        url.path,
        json={"email": victim_outside_product["email"], "code": "000000"},
    )
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)

    # 2. completing over the SMS channel yields the identity
    phone = user_phone_number
    url = client.app.router["auth_register_phone"].url_for()
    response = await client.post(
        url.path,
        json={"email": victim_outside_product["email"], "phone": phone},
    )
    await assert_status(response, status.HTTP_202_ACCEPTED)
    kwargs = mocked_twilio_service["send_sms_code_for_registration"].call_args.kwargs
    received_code = kwargs["code"]

    url = client.app.router["auth_phone_confirmation"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": victim_outside_product["email"],
            "phone": phone,
            "code": received_code,
        },
    )
    await assert_status(response, status.HTTP_200_OK)

    # the identity is now usable
    response = await client.post(logout_url.path, json={})
    assert response.status == status.HTTP_200_OK


async def test_register_new_user_still_granted_on_2fa_product(
    client: TestClient,
    mocked_notifications_service_send_message_from_template,
    cleanup_db_tables: None,
    user_email: str,
    user_password: str,
):
    """Self-registration (attacker-owned email) keeps granting login"""
    assert client.app
    async with NewInvitation(client, guest_email=user_email) as invitation:
        assert invitation.confirmation
        url = client.app.router["auth_register"].url_for()
        response = await client.post(
            url.path,
            json={
                "email": user_email,
                "password": user_password,
                "confirm": user_password,
                "invitation": invitation.confirmation["code"],
            },
        )
    await assert_status(response, status.HTTP_200_OK)
    user = await _auth_service.get_user_or_none(client.app, email=user_email)
    assert user is not None
    assert user["status"] == UserStatus.ACTIVE.name


@pytest.mark.parametrize(
    "guest_email,raises",
    [
        pytest.param("alice@acme.com", True, id="email mismatch"),
        pytest.param(None, False, id="legacy unbound"),
    ],
)
async def test_db_invitation_email_binding(
    client: TestClient,
    victim_outside_product: UserInfoDict,
    guest_email: str | None,
    raises: bool,
):
    """A DB invitation code whose guest tag is another email cannot register"""
    assert client.app
    code = await _create_invitation_code(client, victim_outside_product, guest_email=guest_email)

    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": victim_outside_product["email"],
            "password": DEFAULT_TEST_PASSWORD,  # victim's real password
            "invitation": code,
        },
    )
    if raises:
        await assert_status(response, status.HTTP_403_FORBIDDEN)
    else:
        # unbound legacy code: accepted at consumption, flow continues with 2FA
        await assert_status(response, status.HTTP_202_ACCEPTED)


async def test_db_invitation_product_binding(
    client: TestClient,
    app_products_names: list[ProductName],
    victim_outside_product: UserInfoDict,
):
    assert client.app
    product_a, product_b = app_products_names[0], app_products_names[1]
    assert product_a == "osparc"

    # code bound to another product -> rejected in product_a's deployment
    code = await _create_invitation_code(client, victim_outside_product, product=product_b)
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": victim_outside_product["email"],
            "password": DEFAULT_TEST_PASSWORD,
            "invitation": code,
        },
    )
    await assert_status(response, status.HTTP_403_FORBIDDEN)
