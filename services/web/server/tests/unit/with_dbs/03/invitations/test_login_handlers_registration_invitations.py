# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from urllib import parse

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationInputs,
)
from models_library.products import ProductName
from pydantic import HttpUrl
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.invitations.api import generate_invitation
from simcore_service_webserver.login.handlers_registration import (
    InvitationCheck,
    InvitationInfo,
)
from simcore_service_webserver.login.settings import LoginSettingsForProduct
from yarl import URL


async def test_check_registration_invitation_when_not_required(
    client: TestClient,
    mocker: MockerFixture,
):
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    assert client.app
    assert (
        client.app.router["auth_check_registration_invitation"].url_for().path
        == "/v0/auth/register/invitations:check"
    )

    response = await client.post(
        "/v0/auth/register/invitations:check",
        json=InvitationCheck(invitation="*" * 100).dict(),
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email is None


async def test_check_registration_invitations_with_old_code(
    client: TestClient,
    mocker: MockerFixture,
):
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct.create_from_envs(
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,  # <--
        ),
    )

    response = await client.post(
        "/v0/auth/register/invitations:check",
        json=InvitationCheck(invitation="short-code").dict(),
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email is None


@pytest.mark.acceptance_test()
async def test_check_registration_invitation_and_get_email(
    client: TestClient,
    mocker: MockerFixture,
    mock_invitations_service_http_api: AioResponsesMock,
    fake_osparc_invitation: ApiInvitationContent,
):

    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct.create_from_envs(
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,  # <--
        ),
    )

    response = await client.post(
        "/v0/auth/register/invitations:check",
        json=InvitationCheck(invitation="*" * 105).dict(),
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email == fake_osparc_invitation.guest


def _extract_invitation_code_from_url(invitation_url: HttpUrl) -> str:
    assert invitation_url.fragment
    query_params = dict(parse.parse_qsl(URL(invitation_url.fragment).query))
    return query_params["invitation"]


@pytest.mark.acceptance_test()
async def test_registration_to_different_product(
    mocker: MockerFixture,
    faker: Faker,
    all_products_names: list[ProductName],
    client: TestClient,
):
    assert client.app

    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,
            LOGIN_TWILIO=None,
        ),
    )

    guest_email = faker.email()
    guest_password = "secret" * 3

    async def _register_account(invitation_url: HttpUrl):
        assert client.app
        url = client.app.router["auth_register"].url_for()

        return await client.post(
            url.path,
            json={
                "email": guest_email,
                "password": guest_password,
                "confirm": guest_password,
                "invitation": _extract_invitation_code_from_url(invitation_url),
            },
        )

    product_a = all_products_names[0]
    product_b = all_products_names[1]

    # 1. PO creates an invitation for product A
    invitation_product_a = await generate_invitation(
        client.app,
        ApiInvitationInputs(issuer="testcase1", guest=guest_email, product=product_a),
    )
    # guest registers for product A
    response = await _register_account(invitation_product_a.invitation_url)
    await assert_status(response, web.HTTPOk)

    # 2. PO creates invitation for product B
    invitation_product_b = await generate_invitation(
        client.app,
        ApiInvitationInputs(issuer="testcase2", guest=guest_email, product=product_b),
    )
    # guest registers for product B
    response = await _register_account(invitation_product_b.invitation_url)
    await assert_status(response, web.HTTPOk)

    # 3. Guest cannot re-register in product A
    response = await _register_account(invitation_product_a.invitation_url)
    await assert_status(response, web.HTTPConflict)

    # TODO: disable account -> cannot register anymore
    # TODO: add expiration to invitations (e.g if user is removed from a product, the same user could reuse old invitation to reactivate product)
