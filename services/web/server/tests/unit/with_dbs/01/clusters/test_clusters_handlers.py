# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements


import json
import random
from http import HTTPStatus
from typing import Any

import hypothesis
import hypothesis.provisional
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from hypothesis import strategies as st
from models_library.api_schemas_webserver.clusters import (
    ClusterCreate,
    ClusterPatch,
    ClusterPing,
)
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    Cluster,
    ClusterTypeInModel,
    SimpleAuthentication,
)
from pydantic import HttpUrl, TypeAdapter
from pydantic_core import Url
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import (  # nopycln: import
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_postgres_database.models.clusters import ClusterType
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.director_v2.exceptions import (
    ClusterAccessForbidden,
    ClusterNotFoundError,
    ClusterPingError,
    DirectorServiceError,
)


@st.composite
def http_url_strategy(draw):
    return TypeAdapter(HttpUrl).validate_python(draw(hypothesis.provisional.urls()))


@st.composite
def cluster_patch_strategy(draw):
    return ClusterPatch(
        name=draw(st.text()),
        description=draw(st.text()),
        owner=draw(st.integers(min_value=1)),
        type=draw(st.sampled_from(ClusterTypeInModel)),
        thumbnail=draw(http_url_strategy()),
        endpoint=draw(http_url_strategy()),
        authentication=None,
        accessRights={},
    )


st.register_type_strategy(ClusterPatch, cluster_patch_strategy())
st.register_type_strategy(Url, http_url_strategy())


@pytest.fixture
def mocked_director_v2_api(mocker: MockerFixture):
    mocked_director_v2_api = mocker.patch(
        "simcore_service_webserver.clusters._handlers.director_v2_api", autospec=True
    )

    mocked_director_v2_api.create_cluster.return_value = random.choice(
        Cluster.model_config["json_schema_extra"]["examples"]
    )
    mocked_director_v2_api.list_clusters.return_value = []
    mocked_director_v2_api.get_cluster.return_value = random.choice(
        Cluster.model_config["json_schema_extra"]["examples"]
    )
    mocked_director_v2_api.get_cluster_details.return_value = {
        "scheduler": {"status": "running"},
        "dashboardLink": "https://link.to.dashboard",
    }
    mocked_director_v2_api.update_cluster.return_value = random.choice(
        Cluster.model_config["json_schema_extra"]["examples"]
    )
    mocked_director_v2_api.delete_cluster.return_value = None
    mocked_director_v2_api.ping_cluster.return_value = None
    mocked_director_v2_api.ping_specific_cluster.return_value = None


@pytest.fixture
def mocked_director_v2_with_error(
    mocker: MockerFixture, faker: Faker, director_v2_error: type[DirectorServiceError]
):
    mocked_director_v2_api = mocker.patch(
        "simcore_service_webserver.clusters._handlers.director_v2_api", autospec=True
    )
    error = director_v2_error(
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
        reason="no director-v2",
        url=faker.uri(),
        cluster_id=faker.pyint(min_value=1),
        endpoint=faker.uri(),
    )
    mocked_director_v2_api.create_cluster.side_effect = error
    mocked_director_v2_api.list_clusters.side_effect = error
    mocked_director_v2_api.get_cluster.side_effect = error
    mocked_director_v2_api.get_cluster_details.side_effect = error
    mocked_director_v2_api.update_cluster.side_effect = error
    mocked_director_v2_api.delete_cluster.side_effect = error
    mocked_director_v2_api.ping_cluster.side_effect = error
    mocked_director_v2_api.ping_specific_cluster.side_effect = error


@pytest.fixture()
def cluster_create(faker: Faker) -> ClusterCreate:
    instance = ClusterCreate(
        name=faker.name(),
        endpoint=faker.uri(),
        type=random.choice(list(ClusterType)),
        owner=faker.pyint(),
        authentication=SimpleAuthentication(
            username=faker.user_name(), password=faker.password()
        ),
    )
    assert instance
    return instance


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_cluster(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    faker: Faker,
    cluster_create: ClusterCreate,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    cluster_create.access_rights[logged_user["id"]] = CLUSTER_ADMIN_RIGHTS
    print(f"--> creating {cluster_create=!r}")
    # check we can create a cluster
    assert client.app
    url = client.app.router["create_cluster"].url_for()
    rsp = await client.post(
        f"{url}",
        json=json.loads(cluster_create.model_dump_json(by_alias=True)),
    )
    data, error = await assert_status(
        rsp,
        (
            expected.forbidden if user_role == UserRole.USER else expected.created
        ),  # only accessible for TESTER
    )
    if error:
        # we are done here
        return

    created_cluster = Cluster.model_validate(data)
    assert created_cluster


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_clusters(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    expected: ExpectedResponse,
):
    # check empty clusters
    assert client.app
    url = client.app.router["list_clusters"].url_for()
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, list)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_get_cluster(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    # check not found
    assert client.app
    url = client.app.router["get_cluster"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, dict)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_get_cluster_details(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    # check not found
    assert client.app
    url = client.app.router["get_cluster_details"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, dict)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
@hypothesis.given(cluster_patch=st.from_type(ClusterPatch))
@hypothesis.settings(
    # hypothesis does not play well with fixtures, hence the warning
    # it will create several tests but not replay the fixtures
    suppress_health_check=[
        hypothesis.HealthCheck.function_scoped_fixture,
        hypothesis.HealthCheck.too_slow,
    ],
    deadline=None,
)
async def test_update_cluster(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    cluster_patch: ClusterPatch,
    expected: ExpectedResponse,
):
    print(f"--> updating {cluster_patch=!r}")
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    assert client.app
    url = client.app.router["update_cluster"].url_for(cluster_id=f"{25}")
    rsp = await client.patch(
        f"{url}",
        json=json.loads(cluster_patch.model_dump_json(**_PATCH_EXPORT)),
    )
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, dict)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_delete_cluster(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["delete_cluster"].url_for(cluster_id=f"{25}")
    rsp = await client.delete(f"{url}")
    data, error = await assert_status(rsp, expected.no_content)
    if not error:
        assert data is None


@pytest.mark.parametrize(*standard_role_response(), ids=str)
@hypothesis.given(cluster_ping=st.from_type(ClusterPing))
@hypothesis.settings(
    # hypothesis does not play well with fixtures, hence the warning
    # it will create several tests but not replay the fixtures
    suppress_health_check=[
        hypothesis.HealthCheck.function_scoped_fixture,
        hypothesis.HealthCheck.too_slow,
    ],
    deadline=None,
)
async def test_ping_cluster(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    expected: ExpectedResponse,
    cluster_ping: ClusterPing,
):
    print(f"--> pinging {cluster_ping=!r}")
    assert client.app
    url = client.app.router["ping_cluster"].url_for()
    rsp = await client.post(
        f"{url}", json=json.loads(cluster_ping.model_dump_json(by_alias=True))
    )
    data, error = await assert_status(rsp, expected.no_content)
    if not error:
        assert data is None


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_ping_specific_cluster(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: dict[str, Any],
    faker: Faker,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["ping_cluster_cluster_id"].url_for(
        cluster_id=f"{faker.pyint(min_value=1)}"
    )
    rsp = await client.post(f"{url}")
    data, error = await assert_status(rsp, expected.no_content)
    if not error:
        assert data is None


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
async def test_create_cluster_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    faker: Faker,
    cluster_create: ClusterCreate,
    expected_http_error: HTTPStatus,
):
    cluster_create.access_rights[logged_user["id"]] = CLUSTER_ADMIN_RIGHTS
    print(f"--> creating {cluster_create=!r}")
    # check we can create a cluster
    assert client.app
    url = client.app.router["create_cluster"].url_for()
    rsp = await client.post(
        f"{url}",
        json=json.loads(cluster_create.model_dump_json(by_alias=True)),
    )
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
async def test_list_clusters_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    expected_http_error: HTTPStatus,
):
    # check empty clusters
    assert client.app
    url = client.app.router["list_clusters"].url_for()
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ClusterNotFoundError, status.HTTP_404_NOT_FOUND),
        (ClusterAccessForbidden, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_get_cluster_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    expected_http_error: HTTPStatus,
):
    # check empty clusters
    assert client.app
    url = client.app.router["get_cluster"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ClusterNotFoundError, status.HTTP_404_NOT_FOUND),
        (ClusterAccessForbidden, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_get_cluster_details_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    expected_http_error: HTTPStatus,
):
    # check not found
    assert client.app
    url = client.app.router["get_cluster_details"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ClusterNotFoundError, status.HTTP_404_NOT_FOUND),
        (ClusterAccessForbidden, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_update_cluster_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    expected_http_error: HTTPStatus,
):
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    assert client.app
    url = client.app.router["update_cluster"].url_for(cluster_id=f"{25}")
    rsp = await client.patch(
        f"{url}",
        json=json.loads(ClusterPatch().model_dump_json(**_PATCH_EXPORT)),
    )
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ClusterNotFoundError, status.HTTP_404_NOT_FOUND),
        (ClusterAccessForbidden, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_delete_cluster_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    expected_http_error: HTTPStatus,
):
    assert client.app
    url = client.app.router["delete_cluster"].url_for(cluster_id=f"{25}")
    rsp = await client.delete(f"{url}")
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ClusterPingError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    ],
)
async def test_ping_cluster_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    faker: Faker,
    expected_http_error,
):
    cluster_ping = ClusterPing(
        endpoint=faker.uri(),
        authentication=SimpleAuthentication(
            username=faker.user_name(), password=faker.password()
        ),
    )
    assert client.app
    url = client.app.router["ping_cluster"].url_for()
    rsp = await client.post(
        f"{url}", json=json.loads(cluster_ping.model_dump_json(by_alias=True))
    )
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error


@pytest.mark.parametrize("user_role", [UserRole.TESTER], ids=str)
@pytest.mark.parametrize(
    "director_v2_error, expected_http_error",
    [
        (DirectorServiceError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ClusterPingError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    ],
)
async def test_ping_specific_cluster_with_error(
    enable_webserver_clusters_feature: None,
    mocked_director_v2_with_error,
    client: TestClient,
    logged_user: dict[str, Any],
    faker: Faker,
    expected_http_error,
):
    assert client.app
    url = client.app.router["ping_cluster_cluster_id"].url_for(
        cluster_id=f"{faker.pyint(min_value=1)}"
    )
    rsp = await client.post(f"{url}")
    data, error = await assert_status(rsp, expected_http_error)
    assert not data
    assert error
