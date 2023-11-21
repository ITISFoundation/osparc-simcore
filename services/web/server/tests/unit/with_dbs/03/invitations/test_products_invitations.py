# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from datetime import datetime, timezone

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    InvitationGenerated,
)
from pydantic import PositiveInt
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.users import UserRole


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    env_devel_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_META_MODELING": "0",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STUDIES_ACCESS_ENABLED": "0",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
            "WEBSERVER_WALLETS": "0",
        },
    )

    # undefine WEBSERVER_INVITATIONS
    app_environment.pop("WEBSERVER_INVITATIONS", None)
    monkeypatch.delenv("WEBSERVER_INVITATIONS", raising=False)

    # set INVITATIONS_* variables using those in .devel-env
    envs_invitations = setenvs_from_dict(
        monkeypatch,
        envs={
            name: value
            for name, value in env_devel_dict.items()
            if name.startswith("INVITATIONS_")
        },
    )

    return app_environment | envs_plugins | envs_invitations


@pytest.fixture
def guest_email(faker: Faker) -> str:
    return faker.email()


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPForbidden),
        (UserRole.PRODUCT_OWNER, web.HTTPOk),
        (UserRole.ADMIN, web.HTTPForbidden),
    ],
)
async def test_role_access_to_generate_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    logged_user: UserInfoDict,
    expected_status: type[web.HTTPException],
    guest_email: str,
):
    response = await client.post(
        "/v0/invitation:generate",
        json={
            "guest": guest_email,
        },
    )
    data, error = await assert_status(response, expected_status)
    if data:
        got = InvitationGenerated.parse_obj(data)
        assert got.guest == guest_email
    else:
        assert error


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.PRODUCT_OWNER, web.HTTPOk),
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
    expected_status: type[web.HTTPException],
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
