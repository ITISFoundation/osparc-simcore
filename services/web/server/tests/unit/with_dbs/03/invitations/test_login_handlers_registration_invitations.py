# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationInputs,
)
from models_library.products import ProductName
from pydantic import HttpUrl
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
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
        json=InvitationCheck(invitation="*" * 100).model_dump(),
    )
    data, _ = await assert_status(response, status.HTTP_200_OK)

    invitation = InvitationInfo.model_validate(data)
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
        json=InvitationCheck(invitation="short-code").model_dump(),
    )
    data, _ = await assert_status(response, status.HTTP_200_OK)

    invitation = InvitationInfo.model_validate(data)
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
        json=InvitationCheck(invitation="*" * 105).model_dump(),
    )
    data, _ = await assert_status(response, status.HTTP_200_OK)

    invitation = InvitationInfo.model_validate(data)
    assert invitation.email == fake_osparc_invitation.guest


def _extract_invitation_code_from_url(invitation_url: HttpUrl) -> str:
    assert invitation_url.fragment
    query_params = dict(URL(invitation_url.fragment).query)
    return query_params["invitation"]


@pytest.mark.acceptance_test()
async def test_registration_to_different_product(
    mocker: MockerFixture,
    all_products_names: list[ProductName],
    client: TestClient,
    guest_email: str,
    guest_password: str,
    mock_invitations_service_http_api: AioResponsesMock,
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

    async def _register_account(invitation_url: HttpUrl, product_deployed: ProductName):
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
            headers={X_PRODUCT_NAME_HEADER: product_deployed},
        )

    product_a = all_products_names[0]
    product_b = all_products_names[1]

    # PO creates an two invitations for guest in product A and product B
    invitation_product_a = await generate_invitation(
        client.app,
        ApiInvitationInputs(issuer="PO", guest=guest_email, product=product_a),
    )
    # 2. PO creates invitation for product B
    invitation_product_b = await generate_invitation(
        client.app,
        ApiInvitationInputs(issuer="PO", guest=guest_email, product=product_b),
    )

    # CAN register for product A in deploy of product A
    response = await _register_account(invitation_product_a.invitation_url, product_a)
    await assert_status(response, status.HTTP_200_OK)

    # CANNOT register in product B in deploy of product A
    response = await _register_account(invitation_product_b.invitation_url, product_a)
    await assert_status(response, status.HTTP_409_CONFLICT)

    # CAN register for product B in deploy of product B
    response = await _register_account(invitation_product_b.invitation_url, product_b)
    await assert_status(response, status.HTTP_200_OK)

    # CANNOT re-register in product
    response = await _register_account(invitation_product_b.invitation_url, product_b)
    await assert_status(response, status.HTTP_409_CONFLICT)
