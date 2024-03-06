# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from datetime import datetime, timezone
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    InvitationGenerated,
)
from pydantic import PositiveInt
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
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
        got = InvitationGenerated.parse_obj(data)
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
        json=request_model.dict(exclude_none=True),
    )

    # checks
    data, error = await assert_status(response, expected_status)
    assert not error

    got = InvitationGenerated.parse_obj(data)
    expected = {"issuer": logged_user["email"], **request_model.dict(exclude_none=True)}
    assert got.dict(include=set(expected), by_alias=False) == expected

    product_base_url = f"{client.make_url('/')}"
    assert got.invitation_link.startswith(product_base_url)
    assert before_dt < got.created
    assert got.created < datetime.now(tz=timezone.utc)


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.PRODUCT_OWNER, web.HTTPOk),
    ],
)
async def test_pre_registration_and_invitation_workflow(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    logged_user: UserInfoDict,
    expected_status: type[web.HTTPException],
    guest_email: str,
    faker: Faker,
):
    requester_info = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": guest_email,
        "companyName": faker.company(),
        "phone": faker.phone_number(),
        "billingAddress": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "state": faker.state(),
        "postalCode": faker.postcode(),
        "country": faker.country(),
    }

    invitation = GenerateInvitation(
        guest=guest_email,
        trial_account_days=None,
        extra_credits_in_usd=10,
    ).dict()

    # Search user -> nothing
    response = await client.get("/v0/users:search", params={"email": guest_email})
    data, _ = await assert_status(response, expected_status)
    # i.e. no info of requester is found, i.e. needs pre-registration
    assert data == []

    # Cannot generate anymore an invitation for users that are not registered or pre-registered
    response = await client.post("/v0/invitation:generate", json=invitation)
    assert response.status == status.HTTP_409_CONFLICT

    # Accept user for registration and create invitation for her
    response = await client.post("/v0/users:pre-register", json=requester_info)
    data, _ = await assert_status(response, expected_status)

    # Search user again
    response = await client.get("/v0/users:search", params={"email": guest_email})
    data, _ = await assert_status(response, expected_status)
    assert len(data) == 1
    assert not data[0]["registered"]
    assert data[0]["email"] == guest_email

    # now i can make as many invitations
    for _ in range(2):
        response = await client.post("/v0/invitation:generate", json=invitation)
        data, _ = await assert_status(response, web.HTTPOk)
        assert data["guest"] == guest_email
