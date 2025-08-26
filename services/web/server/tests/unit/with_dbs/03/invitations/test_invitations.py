# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_invitations.invitations import ApiInvitationContent
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.webserver_login import NewUser
from simcore_service_webserver.groups.api import auto_add_user_to_product_group
from simcore_service_webserver.invitations._client import (
    InvitationsServiceApi,
    get_invitations_service_api,
)
from simcore_service_webserver.invitations.api import validate_invitation_url
from simcore_service_webserver.invitations.errors import (
    InvalidInvitationError,
    InvitationsServiceUnavailableError,
)
from simcore_service_webserver.products.models import Product
from yarl import URL


async def test_invitation_service_unavailable(
    client: TestClient,
    fake_osparc_invitation: ApiInvitationContent,
    current_product: Product,
):
    assert client.app
    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    assert not await invitations_api.ping()

    with pytest.raises(InvitationsServiceUnavailableError):
        await validate_invitation_url(
            app=client.app,
            guest_email=fake_osparc_invitation.guest,
            invitation_url="https://server.com#/registration?invitation=1234",
            current_product=current_product,
        )


async def test_invitation_service_api_ping(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    base_url: URL,
):
    assert client.app
    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    # first request is mocked to pass
    assert await invitations_api.ping()

    # second request is mocked to fail (since mock only works once)
    assert not await invitations_api.is_responsive()

    mock_invitations_service_http_api.assert_called()


async def test_valid_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    fake_osparc_invitation: ApiInvitationContent,
    current_product: Product,
):
    assert client.app
    invitation = await validate_invitation_url(
        app=client.app,
        guest_email=fake_osparc_invitation.guest,
        invitation_url="https://server.com#register?invitation=1234",
        current_product=current_product,
    )
    assert invitation
    assert invitation == fake_osparc_invitation
    mock_invitations_service_http_api.assert_called_once()


async def test_invalid_invitation_if_guest_is_already_registered_in_product(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    fake_osparc_invitation: ApiInvitationContent,
    current_product: Product,
    mocker: MockerFixture,
):
    assert client.app
    kwargs = {
        "app": client.app,
        "guest_email": fake_osparc_invitation.guest,
        "invitation_url": "https://server.com#register?invitation=1234",
        "current_product": current_product,
    }

    # user exists, and we skip product registration to do this test
    mocker.patch(
        "pytest_simcore.helpers.webserver_users.groups_service.auto_add_user_to_product_group",
        return_value=f"Mocked in {__file__}. SKIPPED auto_add_user_to_product_group",
        autospec=True,
    )
    async with NewUser(
        user_data={
            "name": "test-user",
            "email": fake_osparc_invitation.guest,
        },
        app=client.app,
    ) as user:

        # valid because user is not assigned to product
        assert await validate_invitation_url(**kwargs) == fake_osparc_invitation

        # now use is in product
        await auto_add_user_to_product_group(
            client.app, user_id=user["id"], product_name=current_product.name
        )

        # invitation is invalid now
        with pytest.raises(InvalidInvitationError):
            await validate_invitation_url(**kwargs)


async def test_invalid_invitation_if_not_guest(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    fake_osparc_invitation: ApiInvitationContent,
    current_product: Product,
):
    assert client.app
    assert fake_osparc_invitation.guest != "unexpected_guest@email.me"
    with pytest.raises(InvalidInvitationError):
        await validate_invitation_url(
            app=client.app,
            guest_email="unexpected_guest@email.me",
            invitation_url="https://server.com#register?invitation=1234",
            current_product=current_product,
        )
