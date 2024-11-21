# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import functools
import sys
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
import simcore_service_webserver.login._auth_api
from aiohttp.test_utils import TestClient
from aiopg.sa.connection import SAConnection
from faker import Faker
from models_library.api_schemas_webserver.auth import AccountRequestInfo
from models_library.generics import Envelope
from psycopg2 import OperationalError
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import (
    DEFAULT_TEST_PASSWORD,
    random_pre_registration_details,
)
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.models.users import UserRole, UserStatus
from simcore_service_webserver.users._preferences_api import (
    get_frontend_user_preferences_aggregation,
)
from simcore_service_webserver.users._schemas import (
    MAX_BYTES_SIZE_EXTRAS,
    PreUserProfile,
    UserProfile,
)
from simcore_service_webserver.users.schemas import ProfileGet, ProfileUpdate


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disables GC and DB-listener
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
        },
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_get_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    expected: HTTPStatus,
    primary_group: dict[str, Any],
    standard_groups: list[dict[str, Any]],
    all_group: dict[str, str],
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(url.path)
    data, error = await assert_status(resp, expected)

    # check enveloped
    e = Envelope[ProfileGet].model_validate(await resp.json())
    assert e.error == error
    assert (
        e.data.model_dump(**RESPONSE_MODEL_POLICY, mode="json") == data
        if e.data
        else e.data == data
    )

    if not error:
        profile = ProfileGet.model_validate(data)

        product_group = {
            "accessRights": {"delete": False, "read": False, "write": False},
            "description": "osparc product group",
            "gid": 2,
            "inclusionRules": {},
            "label": "osparc",
            "thumbnail": None,
        }

        assert profile.login == logged_user["email"]
        assert profile.gravatar_id
        assert profile.first_name == logged_user.get("first_name", None)
        assert profile.last_name == logged_user.get("last_name", None)
        assert profile.role == user_role.name
        assert profile.groups

        got_profile_groups = profile.groups.model_dump(
            **RESPONSE_MODEL_POLICY, mode="json"
        )
        assert got_profile_groups["me"] == primary_group
        assert got_profile_groups["all"] == all_group

        sorted_by_group_id = functools.partial(sorted, key=lambda d: d["gid"])
        assert sorted_by_group_id(
            got_profile_groups["organizations"]
        ) == sorted_by_group_id([*standard_groups, product_group])

        assert profile.preferences == await get_frontend_user_preferences_aggregation(
            client.app, user_id=logged_user["id"], product_name="osparc"
        )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_update_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["update_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.put(url.path, json={"last_name": "Foo"})
    _, error = await assert_status(resp, expected)

    if not error:
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)

        # This is a PUT! i.e. full replace of profile variable fields!
        assert data["first_name"] == ProfileUpdate.model_fields["first_name"].default
        assert data["last_name"] == "Foo"
        assert data["role"] == user_role.name


@pytest.fixture
def mock_failing_database_connection(mocker: Mock) -> MagicMock:
    """
    async with engine.acquire() as conn:
        await conn.execute(query)  --> will raise OperationalError
    """
    # See http://initd.org/psycopg/docs/module.html
    conn_execute = mocker.patch.object(SAConnection, "execute")
    conn_execute.side_effect = OperationalError(
        "MOCK: server closed the connection unexpectedly"
    )
    return conn_execute


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
async def test_get_profile_with_failing_db_connection(
    logged_user: UserInfoDict,
    client: TestClient,
    mock_failing_database_connection: MagicMock,
    expected: HTTPStatus,
):
    """
    Reproduces issue https://github.com/ITISFoundation/osparc-simcore/pull/1160

    A logged user fails to get profie because though authentication because

    i.e. conn.execute(query) will raise psycopg2.OperationalError: server closed the connection unexpectedly

    SEE:
    - https://github.com/ITISFoundation/osparc-simcore/issues/880
    - https://github.com/ITISFoundation/osparc-simcore/pull/1160
    """
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert str(url) == "/v0/me"

    resp = await client.get(url.path)

    data, error = await assert_status(resp, expected)
    assert not data
    assert error["message"] == "Authentication service is temporary unavailable"


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *(
            (role, status.HTTP_403_FORBIDDEN)
            for role in UserRole
            if role not in {UserRole.PRODUCT_OWNER, UserRole.ANONYMOUS}
        ),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
    ],
)
async def test_only_product_owners_can_access_users_api(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["search_users"].url_for()
    assert url.path == "/v0/users:search"

    resp = await client.get(url.path, params={"email": "do-not-exists@foo.com"})
    await assert_status(resp, expected)


@pytest.fixture
def account_request_form(faker: Faker) -> dict[str, Any]:
    # This is AccountRequestInfo.form
    form = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": faker.email(),
        "phone": faker.phone_number(),
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
    assert set(form) == set(
        AccountRequestInfo.model_config["json_schema_extra"]["example"]["form"]
    )
    return form


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
async def test_search_and_pre_registration(
    client: TestClient,
    logged_user: UserInfoDict,
    account_request_form: dict[str, Any],
):
    assert client.app

    # ONLY in `users` and NOT `users_pre_registration_details`
    resp = await client.get("/v0/users:search", params={"email": logged_user["email"]})
    assert resp.status == status.HTTP_200_OK

    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserProfile(
        **found[0],
        institution=None,
        address=None,
        city=None,
        state=None,
        postal_code=None,
        country=None,
    )
    expected = {
        "first_name": logged_user.get("first_name"),
        "last_name": logged_user.get("last_name"),
        "email": logged_user["email"],
        "institution": None,
        "phone": logged_user.get("phone"),
        "address": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
        "extras": {},
        "registered": True,
        "status": UserStatus.ACTIVE,
    }
    assert got.model_dump(include=set(expected)) == expected

    # NOT in `users` and ONLY `users_pre_registration_details`

    # create pre-registration
    resp = await client.post("/v0/users:pre-register", json=account_request_form)
    assert resp.status == status.HTTP_200_OK

    resp = await client.get(
        "/v0/users:search", params={"email": account_request_form["email"]}
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserProfile(**found[0], state=None, status=None)

    assert got.model_dump(include={"registered", "status"}) == {
        "registered": False,
        "status": None,
    }

    # Emulating registration of pre-register user
    new_user = (
        await simcore_service_webserver.login._auth_api.create_user(  # noqa: SLF001
            client.app,
            email=account_request_form["email"],
            password=DEFAULT_TEST_PASSWORD,
            status_upon_creation=UserStatus.ACTIVE,
            expires_at=None,
        )
    )

    resp = await client.get(
        "/v0/users:search", params={"email": account_request_form["email"]}
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    got = UserProfile(**found[0], state=None)
    assert got.model_dump(include={"registered", "status"}) == {
        "registered": True,
        "status": new_user["status"].name,
    }


@pytest.mark.parametrize(
    "institution_key",
    [
        "institution",
        "companyName",
        "company",
        "university",
        "universityName",
    ],
)
def test_preuserprofile_parse_model_from_request_form_data(
    account_request_form: dict[str, Any],
    institution_key: str,
):
    data = deepcopy(account_request_form)
    data[institution_key] = data.pop("company")
    data["comment"] = "extra comment"

    # pre-processors
    pre_user_profile = PreUserProfile(**data)

    print(pre_user_profile.model_dump_json(indent=1))

    # institution aliases
    assert pre_user_profile.institution == account_request_form["company"]

    # extras
    assert {
        "application",
        "description",
        "hear",
        "privacyPolicy",
        "eula",
        "comment",
    } == set(pre_user_profile.extras)
    assert pre_user_profile.extras["comment"] == "extra comment"


def test_preuserprofile_parse_model_without_extras(
    account_request_form: dict[str, Any]
):
    required = {
        f.alias or f_name
        for f_name, f in PreUserProfile.model_fields.items()
        if f.is_required()
    }
    data = {k: account_request_form[k] for k in required}
    assert not PreUserProfile(**data).extras


def test_preuserprofile_max_bytes_size_extras_limits(faker: Faker):
    data = random_pre_registration_details(faker)
    data_size = sys.getsizeof(data["extras"])

    assert data_size < MAX_BYTES_SIZE_EXTRAS


@pytest.mark.parametrize(
    "given_name", ["PEDrO-luis", "pedro luis", "   pedro  LUiS   ", "pedro  lUiS   "]
)
def test_preuserprofile_pre_given_names(
    given_name: str,
    account_request_form: dict[str, Any],
):
    account_request_form["firstName"] = given_name
    account_request_form["lastName"] = given_name

    pre_user_profile = PreUserProfile(**account_request_form)
    print(pre_user_profile.model_dump_json(indent=1))
    assert pre_user_profile.first_name in ["Pedro-Luis", "Pedro Luis"]
    assert pre_user_profile.first_name == pre_user_profile.last_name
