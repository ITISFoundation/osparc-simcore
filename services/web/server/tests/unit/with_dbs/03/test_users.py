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
from models_library.api_schemas_webserver.users import MyProfileGet, UserGet
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
    PreRegisteredUserGet,
)


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
        *((r, status.HTTP_200_OK) for r in UserRole if r >= UserRole.GUEST),
    ],
)
async def test_access_rights_on_get_profile(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(f"{url}")
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        *((r, status.HTTP_204_NO_CONTENT) for r in UserRole if r >= UserRole.USER),
    ],
)
async def test_access_update_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["update_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.patch(f"{url}", json={"last_name": "Foo"})
    await assert_status(resp, expected)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    primary_group: dict[str, Any],
    standard_groups: list[dict[str, Any]],
    all_group: dict[str, str],
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, status.HTTP_200_OK)

    resp_model = Envelope[MyProfileGet].model_validate(await resp.json())

    assert resp_model.data.model_dump(**RESPONSE_MODEL_POLICY, mode="json") == data
    assert resp_model.error is None

    profile = resp_model.data

    product_group = {
        "accessRights": {"delete": False, "read": False, "write": False},
        "description": "osparc product group",
        "gid": 2,
        "inclusionRules": {},
        "label": "osparc",
        "thumbnail": None,
    }

    assert profile.login == logged_user["email"]
    assert profile.first_name == logged_user.get("first_name", None)
    assert profile.last_name == logged_user.get("last_name", None)
    assert profile.role == user_role.name
    assert profile.groups

    got_profile_groups = profile.groups.model_dump(**RESPONSE_MODEL_POLICY, mode="json")
    assert got_profile_groups["me"] == primary_group
    assert got_profile_groups["all"] == all_group

    sorted_by_group_id = functools.partial(sorted, key=lambda d: d["gid"])
    assert sorted_by_group_id(
        got_profile_groups["organizations"]
    ) == sorted_by_group_id([*standard_groups, product_group])

    assert profile.preferences == await get_frontend_user_preferences_aggregation(
        client.app, user_id=logged_user["id"], product_name="osparc"
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_update_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
):
    assert client.app

    resp = await client.get("/v0/me")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    assert data["role"] == user_role.name
    before = deepcopy(data)

    url = client.app.router["update_my_profile"].url_for()
    assert url.path == "/v0/me"
    resp = await client.patch(
        f"{url}",
        json={
            "last_name": "Foo",
        },
    )
    _, error = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    assert not error

    resp = await client.get("/v0/me")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    assert data["last_name"] == "Foo"

    def _copy(data: dict, exclude: set) -> dict:
        return {k: v for k, v in data.items() if k not in exclude}

    exclude = {"last_name"}
    assert _copy(data, exclude) == _copy(before, exclude)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_profile_workflow(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    my_profile = MyProfileGet.model_validate(data)

    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "first_name": "Odei",  # NOTE: still not camecase!
            "userName": "odei123",
            "privacy": {"hideFullname": False},
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    updated_profile = MyProfileGet.model_validate(data)

    assert updated_profile.first_name != my_profile.first_name
    assert updated_profile.last_name == my_profile.last_name
    assert updated_profile.login == my_profile.login

    assert updated_profile.user_name != my_profile.user_name
    assert updated_profile.user_name == "odei123"

    assert updated_profile.privacy != my_profile.privacy
    assert updated_profile.privacy.hide_email == my_profile.privacy.hide_email
    assert updated_profile.privacy.hide_fullname != my_profile.privacy.hide_fullname


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize("invalid_username", ["", "_foo", "superadmin", "foo..-123"])
async def test_update_wrong_user_name(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    invalid_username: str,
):
    assert client.app

    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "userName": invalid_username,
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_update_existing_user_name(
    user: UserInfoDict,
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
):
    assert client.app

    other_username = user["name"]
    assert other_username != logged_user["name"]

    #  update with SAME username (i.e. existing)
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    assert data["userName"] == logged_user["name"]

    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "userName": other_username,
        },
    )
    await assert_status(resp, status.HTTP_409_CONFLICT)


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
async def test_access_rights_on_search_users_only_product_owners_can_access(
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
    got = UserGet(
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
    got = UserGet(**found[0], state=None, status=None)

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
    got = UserGet(**found[0], state=None)
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
    pre_user_profile = PreRegisteredUserGet(**data)

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
        for f_name, f in PreRegisteredUserGet.model_fields.items()
        if f.is_required()
    }
    data = {k: account_request_form[k] for k in required}
    assert not PreRegisteredUserGet(**data).extras


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

    pre_user_profile = PreRegisteredUserGet(**account_request_form)
    print(pre_user_profile.model_dump_json(indent=1))
    assert pre_user_profile.first_name in ["Pedro-Luis", "Pedro Luis"]
    assert pre_user_profile.first_name == pre_user_profile.last_name
