# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_error, assert_status
from pytest_simcore.helpers.utils_login import NewInvitation, NewUser, parse_link
from servicelib.aiohttp.rest_responses import unwrap_envelope
from simcore_service_webserver.db_models import ConfirmationAction, UserStatus
from simcore_service_webserver.login.registration import get_confirmation_info
from simcore_service_webserver.login.settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
)
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage

EMAIL, PASSWORD = "tester@test.com", "password"


@pytest.fixture
def cfg(client: TestClient) -> LoginOptions:
    cfg = get_plugin_options(client.app)
    assert cfg
    return cfg


@pytest.fixture
def db(client: TestClient) -> AsyncpgStorage:
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


# TESTS ---------------------------------------------------------------------------


async def test_regitration_availibility(client: TestClient):
    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        url,
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )

    await assert_status(r, web.HTTPOk)


async def test_regitration_is_not_get(client: TestClient):
    url = client.app.router["auth_register"].url_for()
    r = await client.get(url)
    await assert_error(r, web.HTTPMethodNotAllowed)


async def test_registration_with_existing_email(client: TestClient, cfg: LoginOptions):
    url = client.app.router["auth_register"].url_for()
    async with NewUser(app=client.app) as user:
        r = await client.post(
            url,
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
    await assert_error(r, web.HTTPConflict, cfg.MSG_EMAIL_EXISTS)


@pytest.mark.skip("TODO: Feature still not implemented")
async def test_registration_with_expired_confirmation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    mocker,
):
    mocker.patch(
        "simcore_service_webserver.login.settings.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,
        ),
    )

    url = client.app.router["auth_register"].url_for()

    async with NewUser({"status": UserStatus.CONFIRMATION_PENDING.name}) as user:
        confirmation = await db.create_confirmation(
            user, ConfirmationAction.REGISTRATION.name
        )
        r = await client.post(
            url,
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
        await db.delete_confirmation(confirmation)

    await assert_error(r, web.HTTPConflict, cfg.MSG_EMAIL_EXISTS)


async def test_registration_without_confirmation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    mocker,
):
    mocker.patch(
        "simcore_service_webserver.login.handlers.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
        ),
    )

    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        url, json={"email": EMAIL, "password": PASSWORD, "confirm": PASSWORD}
    )
    data, error = unwrap_envelope(await r.json())

    assert r.status == 200, (data, error)
    assert cfg.MSG_LOGGED_IN in data["message"]

    user = await db.get_user({"email": EMAIL})
    assert user
    await db.delete_user(user)


async def test_registration_with_confirmation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    capsys,
    mocker,
):
    mocker.patch(
        "simcore_service_webserver.login.handlers.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
        ),
    )

    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        url, json={"email": EMAIL, "password": PASSWORD, "confirm": PASSWORD}
    )
    data, error = unwrap_envelope(await r.json())
    assert r.status == 200, (data, error)

    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.CONFIRMATION_PENDING.name

    assert "verification link" in data["message"]

    # retrieves sent link by email (see monkeypatch of email in conftest.py)
    out, err = capsys.readouterr()
    link = parse_link(out)
    assert "/auth/confirmation/" in str(link)
    resp = await client.get(link)
    text = await resp.text()

    assert (
        "This is a result of disable_static_webserver fixture for product OSPARC"
        in text
    )
    assert resp.status == 200

    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.ACTIVE.name
    await db.delete_user(user)


@pytest.mark.parametrize(
    "is_invitation_required,has_valid_invitation,expected_response",
    [
        (True, True, web.HTTPOk),
        (True, False, web.HTTPForbidden),
        (False, True, web.HTTPOk),
        (False, False, web.HTTPOk),
    ],
)
async def test_registration_with_invitation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    is_invitation_required,
    has_valid_invitation,
    expected_response,
    mocker,
):
    mocker.patch(
        "simcore_service_webserver.login.handlers.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=is_invitation_required,
        ),
    )

    #
    # User gets an email with a link as
    #   https:/some-web-address.io/#/registration/?invitation={code}
    #
    # Front end then creates the following request
    #
    async with NewInvitation(client) as confirmation:
        print(get_confirmation_info(cfg, confirmation))

        url = client.app.router["auth_register"].url_for()

        r = await client.post(
            url,
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "confirm": PASSWORD,
                "invitation": confirmation["code"]
                if has_valid_invitation
                else "WRONG_CODE",
            },
        )
        await assert_status(r, expected_response)

        # check optional fields in body
        if not has_valid_invitation or not is_invitation_required:
            r = await client.post(
                url, json={"email": "new-user" + EMAIL, "password": PASSWORD}
            )
            await assert_status(r, expected_response)

        if is_invitation_required and has_valid_invitation:
            assert not await db.get_confirmation(confirmation)
