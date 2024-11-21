# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from datetime import datetime, timezone
from http import HTTPStatus
from typing import Final

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    InvitationGenerated,
)
from models_library.invitations import _MAX_LEN
from pydantic import PositiveInt
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import DEFAULT_TEST_PASSWORD
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_role_access_to_generate_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    logged_user: UserInfoDict,
    expected_status: HTTPStatus,
    guest_email: str,
    faker: Faker,
):
    assert client.app
    assert (
        client.app.router["generate_invitation"].url_for().path
        == "/v0/invitation:generate"
    )

    response = await client.post(
        "/v0/invitation:generate",
        json={"guest": guest_email},
    )
    data, error = await assert_status(response, expected_status)
    if not error:
        got = InvitationGenerated.model_validate(data)
        assert got.guest == guest_email
    else:
        assert error


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
    ],
)
@pytest.mark.parametrize(
    "trial_account_days,extra_credits_in_usd",
    [(3, 10), (None, 10), (None, 0), (3, None), (None, None)],
)
async def test_product_owner_generates_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    logged_user: UserInfoDict,
    guest_email: str,
    expected_status: HTTPStatus,
    trial_account_days: PositiveInt | None,
    extra_credits_in_usd: PositiveInt | None,
):
    before_dt = datetime.now(tz=timezone.utc)

    request_model = GenerateInvitation(
        guest=guest_email,
        trial_account_days=trial_account_days,
        extra_credits_in_usd=extra_credits_in_usd,
    )

    # request
    response = await client.post(
        "/v0/invitation:generate",
        json=request_model.model_dump(exclude_none=True),
    )

    # checks
    data, error = await assert_status(response, expected_status)
    assert not error

    got = InvitationGenerated.model_validate(data)
    expected = {
        "issuer": logged_user["email"][:_MAX_LEN],
        **request_model.model_dump(exclude_none=True),
    }
    assert got.model_dump(include=set(expected), by_alias=False) == expected

    product_base_url = f"{client.make_url('/')}"
    assert f"{got.invitation_link}".startswith(product_base_url)
    assert before_dt < got.created
    assert got.created < datetime.now(tz=timezone.utc)


MANY_TIMES: Final = 2


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
    ],
)
async def test_pre_registration_and_invitation_workflow(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    logged_user: UserInfoDict,
    expected_status: HTTPStatus,
    guest_email: str,
    faker: Faker,
):
    requester_info = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": guest_email,
        "companyName": faker.company(),
        "phone": faker.phone_number(),
        # billing info
        "address": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "state": faker.state(),
        "postalCode": faker.postcode(),
        "country": faker.country(),
    }

    invitation = GenerateInvitation(
        guest=guest_email,
        trial_account_days=None,
        extra_credits_in_usd=10,
    ).model_dump()

    # Search user -> nothing
    response = await client.get("/v0/users:search", params={"email": guest_email})
    data, _ = await assert_status(response, expected_status)
    # i.e. no info of requester is found, i.e. needs pre-registration
    assert data == []

    # Cannot generate anymore an invitation for users that are not registered or pre-registered.
    # Cannot do that because otherwise old users willing a new product will not work!
    # response = await client.post("/v0/invitation:generate", json=invitation)
    # assert response.status == status.HTTP_409_CONFLICT

    # Accept user for registration and create invitation for her
    response = await client.post("/v0/users:pre-register", json=requester_info)
    data, _ = await assert_status(response, expected_status)

    # Can only  pre-register once
    for _ in range(MANY_TIMES):
        response = await client.post("/v0/users:pre-register", json=requester_info)
        await assert_status(response, status.HTTP_409_CONFLICT)

    # Search user again
    for _ in range(MANY_TIMES):
        response = await client.get("/v0/users:search", params={"email": guest_email})
        data, _ = await assert_status(response, expected_status)
        assert len(data) == 1
        user_found = data[0]
        assert not user_found["registered"]
        assert user_found["email"] == guest_email

    # Can make as many invitations as I wish
    for _ in range(MANY_TIMES):
        response = await client.post("/v0/invitation:generate", json=invitation)
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert data["guest"] == guest_email
        got_invitation = InvitationGenerated.model_validate(data)

    # register user
    assert got_invitation.invitation_link.fragment
    invitation_code = got_invitation.invitation_link.fragment.split("=")[-1]
    response = await client.post(
        "/v0/auth/register",
        json={
            "email": guest_email,
            "password": DEFAULT_TEST_PASSWORD,
            "confirm": DEFAULT_TEST_PASSWORD,
            "invitation": invitation_code,
        },
    )
    await assert_status(response, status.HTTP_200_OK)

    # find registered user
    response = await client.get("/v0/users:search", params={"email": guest_email})
    data, _ = await assert_status(response, expected_status)
    assert len(data) == 1
    user_found = data[0]
    assert user_found["registered"] is True
    assert user_found["email"] == guest_email
