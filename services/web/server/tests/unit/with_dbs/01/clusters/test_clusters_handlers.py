# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements


import random
from typing import Any, Dict

import hypothesis
import pytest
from _helpers import ExpectedResponse, standard_role_response  # nopycln: import
from aiohttp.test_utils import TestClient
from faker import Faker
from hypothesis import strategies as st
from models_library.clusters import CLUSTER_ADMIN_RIGHTS, Cluster, SimpleAuthentication
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_postgres_database.models.clusters import ClusterType
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.director_v2_models import ClusterCreate, ClusterPatch


@pytest.fixture
def mocked_director_v2_api(mocker: MockerFixture):
    mocked_director_v2_api = mocker.patch(
        "simcore_service_webserver.clusters.handlers.director_v2_api", autospec=True
    )

    mocked_director_v2_api.create_cluster.return_value = Cluster.parse_obj(
        random.choice(Cluster.Config.schema_extra["examples"])
    )
    mocked_director_v2_api.list_clusters.return_value = []
    mocked_director_v2_api.get_cluster.return_value = Cluster.parse_obj(
        random.choice(Cluster.Config.schema_extra["examples"])
    )
    mocked_director_v2_api.update_cluster.return_value = Cluster.parse_obj(
        random.choice(Cluster.Config.schema_extra["examples"])
    )
    mocked_director_v2_api.delete_cluster.return_value = None


@pytest.fixture()
def cluster_create(faker: Faker) -> ClusterCreate:
    instance = ClusterCreate(
        name=faker.name(),
        endpoint=faker.uri(),
        type=random.choice(list(ClusterType)),
        authentication=SimpleAuthentication(
            username=faker.user_name(), password=faker.password()
        ),
    )
    assert instance
    return instance


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_cluster(
    enable_dev_features: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: Dict[str, Any],
    faker: Faker,
    cluster_create: ClusterCreate,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    cluster_create.access_rights[logged_user["id"]] = CLUSTER_ADMIN_RIGHTS
    print(f"--> creating {cluster_create=!r}")
    # check we can create a cluster
    assert client.app
    url = client.app.router["create_cluster_handler"].url_for()
    rsp = await client.post(
        f"{url}", json=cluster_create.dict(by_alias=True, exclude_unset=True)
    )
    data, error = await assert_status(
        rsp,
        expected.forbidden
        if user_role == UserRole.USER
        else expected.created,  # only accessible for TESTER
    )
    if error:
        # we are done here
        return

    created_cluster = Cluster.parse_obj(data)
    assert created_cluster


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_clusters(
    enable_dev_features: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: Dict[str, Any],
    expected: ExpectedResponse,
):
    # check empty clusters
    assert client.app
    url = client.app.router["list_clusters_handler"].url_for()
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, list)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_get_cluster(
    enable_dev_features: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: Dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    # check not found
    assert client.app
    url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, dict)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
@hypothesis.given(cluster_patch=st.from_type(ClusterPatch))
@hypothesis.settings(
    # hypothesis does not play well with fixtures, hence the warning
    # it will create several tests but not replay the fixtures
    suppress_health_check=[hypothesis.HealthCheck.function_scoped_fixture]
)
async def test_update_cluster(
    enable_dev_features: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: Dict[str, Any],
    cluster_patch: ClusterPatch,
    expected: ExpectedResponse,
):
    print(f"--> updating {cluster_patch=!r}")
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    assert client.app
    url = client.app.router["update_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.patch(
        f"{url}",
        json=cluster_patch.dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.ok)
    if not error:
        assert isinstance(data, dict)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_delete_cluster(
    enable_dev_features: None,
    mocked_director_v2_api,
    client: TestClient,
    logged_user: Dict[str, Any],
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["delete_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.delete(f"{url}")
    data, error = await assert_status(rsp, expected.no_content)
    if not error:
        assert data is None
