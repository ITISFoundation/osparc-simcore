# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import random
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List

import httpx
import pytest
import sqlalchemy as sa
from _dask_helpers import DaskGatewayServer
from _pytest.monkeypatch import MonkeyPatch
from dask_gateway import Gateway, GatewayCluster, auth
from distributed import Client as DaskClient
from distributed.deploy.spec import SpecCluster
from faker import Faker
from httpx import URL
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_NO_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
    ClusterAccessRights,
    ExternalClusterAuthentication,
    JupyterHubTokenAuthentication,
    KerberosAuthentication,
    SimpleAuthentication,
)
from pydantic import NonNegativeInt, parse_obj_as
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.clusters import ClusterType, clusters
from simcore_service_director_v2.models.schemas.clusters import (
    ClusterCreate,
    ClusterDetailsOut,
    ClusterOut,
    ClusterPatch,
)
from starlette import status
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture()
def clusters_config(
    mock_env: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitSettings,
    monkeypatch: MonkeyPatch,
    dask_spec_local_cluster: SpecCluster,
):
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_S3_PROVIDER", "MINIO")


@pytest.fixture
async def dask_gateway(
    local_dask_gateway_server: DaskGatewayServer,
) -> Gateway:
    async with Gateway(
        local_dask_gateway_server.address,
        local_dask_gateway_server.proxy_address,
        asynchronous=True,
        auth=auth.BasicAuth("pytest_user", local_dask_gateway_server.password),
    ) as gateway:
        print(f"--> {gateway=} created")
        cluster_options = await gateway.cluster_options()
        gateway_versions = await gateway.get_versions()
        clusters_list = await gateway.list_clusters()
        print(f"--> {gateway_versions=}, {cluster_options=}, {clusters_list=}")
        for option in cluster_options.items():
            print(f"--> {option=}")
        return gateway


@pytest.fixture
async def dask_gateway_cluster(dask_gateway: Gateway) -> AsyncIterator[GatewayCluster]:
    async with dask_gateway.new_cluster() as cluster:
        yield cluster


@pytest.fixture
async def dask_gateway_cluster_client(
    dask_gateway_cluster: GatewayCluster,
) -> AsyncIterator[DaskClient]:
    async with dask_gateway_cluster.get_client() as client:
        yield client


async def test_list_clusters(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    async_client: httpx.AsyncClient,
):
    user_1 = user_db()
    list_clusters_url = URL(f"/v2/clusters?user_id={user_1['id']}")
    # there is no cluster at the moment, the list is empty
    response = await async_client.get(list_clusters_url)
    assert response.status_code == status.HTTP_200_OK
    returned_clusters_list = parse_obj_as(List[ClusterOut], response.json())
    assert returned_clusters_list == []

    # let's create some clusters
    for n in range(111):
        cluster(user_1, name=f"pytest cluster{n:04}")

    response = await async_client.get(list_clusters_url)
    assert response.status_code == status.HTTP_200_OK
    returned_clusters_list = parse_obj_as(List[ClusterOut], response.json())
    assert len(returned_clusters_list) == 111

    # now create a second user and check the clusters are not seen by it
    user_2 = user_db()
    response = await async_client.get(f"/v2/clusters?user_id={user_2['id']}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []

    # let's create a few more clusters owned by user_1 with specific rights
    for rights, name in [
        (CLUSTER_NO_RIGHTS, "no rights"),
        (CLUSTER_USER_RIGHTS, "user rights"),
        (CLUSTER_MANAGER_RIGHTS, "manager rights"),
        (CLUSTER_ADMIN_RIGHTS, "admin rights"),
    ]:
        cluster(
            user_1,  # cluster is owned by user_1
            name=f"cluster with {name}",
            access_rights={
                user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS,
                user_2["primary_gid"]: rights,
            },
        )

    response = await async_client.get(f"/v2/clusters?user_id={user_2['id']}")
    assert response.status_code == status.HTTP_200_OK
    user_2_clusters = parse_obj_as(List[ClusterOut], response.json())
    # we should find 3 clusters
    assert len(user_2_clusters) == 3
    for name in [
        "cluster with user rights",
        "cluster with manager rights",
        "cluster with admin rights",
    ]:
        clusters = list(
            filter(
                lambda cluster, name=name: cluster.name == name,
                user_2_clusters,
            ),
        )
        assert len(clusters) == 1, f"missing cluster with {name=}"


async def test_get_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    async_client: httpx.AsyncClient,
):
    user_1 = user_db()
    # try to get one that does not exist
    response = await async_client.get(
        f"/v2/clusters/15615165165165?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # let's create some clusters
    a_bunch_of_clusters = [
        cluster(user_1, name=f"pytest cluster{n:04}") for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)

    # there is no cluster at the moment, the list is empty
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = parse_obj_as(ClusterOut, response.json())
    assert returned_cluster
    assert the_cluster.dict() == returned_cluster.dict()

    user_2 = user_db()
    # getting the same cluster for user 2 shall return 403
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}"
    )
    assert (
        response.status_code == status.HTTP_403_FORBIDDEN
    ), f"received {response.text}"
    # let's create a few cluster for user 2 and share some with user 1
    for rights, user_1_expected_access in [
        (CLUSTER_NO_RIGHTS, False),
        (CLUSTER_USER_RIGHTS, True),
        (CLUSTER_MANAGER_RIGHTS, True),
        (CLUSTER_ADMIN_RIGHTS, True),
    ]:
        a_cluster = cluster(
            user_2,  # cluster is owned by user_2
            access_rights={
                user_2["primary_gid"]: CLUSTER_ADMIN_RIGHTS,
                user_1["primary_gid"]: rights,
            },
        )
        # now let's check that user_1 can access only the correct ones
        response = await async_client.get(
            f"/v2/clusters/{a_cluster.id}?user_id={user_1['id']}"
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if user_1_expected_access
            else status.HTTP_403_FORBIDDEN
        ), f"received {response.text}"


@pytest.mark.xfail(reason="This needs another iteration and will be tackled next")
async def test_get_default_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    async_client: httpx.AsyncClient,
):
    user_1 = user_db()
    # NOTE: we should not need the user id for default right?
    # NOTE: it should be accessible to everyone to run, and only a handful of elected
    # people shall be able to administer it
    get_cluster_url = URL("/v2/clusters/default")
    response = await async_client.get(get_cluster_url)
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = parse_obj_as(ClusterOut, response.json())
    assert returned_cluster
    assert returned_cluster.name == "Default cluster"
    assert 1 in returned_cluster.access_rights  # everyone group is always 1
    assert returned_cluster.access_rights[1] == CLUSTER_USER_RIGHTS


@pytest.fixture
def cluster_simple_authentication(faker: Faker) -> Callable[[], Dict[str, Any]]:
    def creator() -> Dict[str, Any]:
        simple_auth = {
            "type": "simple",
            "username": faker.user_name(),
            "password": faker.password(),
        }
        assert SimpleAuthentication.parse_obj(simple_auth)
        return simple_auth

    return creator


@pytest.fixture
def cluster_kerberos_authentication(faker: Faker) -> Callable[[], Dict[str, Any]]:
    def creator() -> Dict[str, Any]:
        kerberos_auth = {"type": "kerberos"}
        assert KerberosAuthentication.parse_obj(kerberos_auth)
        return kerberos_auth

    return creator


@pytest.fixture
def cluster_jupyterhub_authentication(faker: Faker) -> Callable[[], Dict[str, Any]]:
    def creator() -> Dict[str, Any]:
        jupyterhub_auth = {"type": "jupyterhub", "api_token": faker.pystr()}
        assert JupyterHubTokenAuthentication.parse_obj(jupyterhub_auth)
        return jupyterhub_auth

    return creator


@pytest.fixture(params=list(ExternalClusterAuthentication.__args__))  # type: ignore
def cluster_authentication(
    cluster_simple_authentication,
    cluster_kerberos_authentication,
    cluster_jupyterhub_authentication,
    request,
) -> Callable[[], Dict[str, Any]]:
    return {
        SimpleAuthentication: cluster_simple_authentication,
        KerberosAuthentication: cluster_kerberos_authentication,
        JupyterHubTokenAuthentication: cluster_jupyterhub_authentication,
    }[request.param]


@pytest.fixture
def clusters_cleaner(postgres_db: sa.engine.Engine) -> Iterator:
    yield
    with postgres_db.connect() as conn:
        conn.execute(sa.delete(clusters))


async def test_create_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
    postgres_db: sa.engine.Engine,
    clusters_cleaner,
):
    user_1 = user_db()
    create_cluster_url = URL(f"/v2/clusters?user_id={user_1['id']}")
    cluster_data = ClusterCreate(
        endpoint=faker.uri(),
        authentication=cluster_simple_authentication(),
        name=faker.name(),
        type=random.choice(list(ClusterType)),
    )
    response = await async_client.post(
        create_cluster_url, json=cluster_data.dict(by_alias=True, exclude_unset=True)
    )
    assert response.status_code == status.HTTP_201_CREATED, f"received: {response.text}"
    created_cluster = parse_obj_as(ClusterOut, response.json())
    assert created_cluster

    for k in created_cluster.dict(exclude={"id", "owner", "access_rights"}).keys():
        assert getattr(created_cluster, k) == getattr(cluster_data, k)

    assert created_cluster.id is not None
    assert created_cluster.owner == user_1["primary_gid"]
    assert created_cluster.access_rights == {
        user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS
    }

    # let's check that DB is correctly setup, there is one entry
    with postgres_db.connect() as conn:
        cluster_entry = conn.execute(
            sa.select([clusters]).where(clusters.c.name == cluster_data.name)
        ).one()


async def test_update_own_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
):
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    user_1 = user_db()
    # try to modify one that does not exist
    response = await async_client.patch(
        f"/v2/clusters/15615165165165?user_id={user_1['id']}",
        json=ClusterPatch().dict(**_PATCH_EXPORT),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # let's create some clusters
    a_bunch_of_clusters = [
        cluster(user_1, name=f"pytest cluster{n:04}") for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)
    # get the original one
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    original_cluster = parse_obj_as(ClusterOut, response.json())

    # now we modify nothing
    response = await async_client.patch(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
        json=ClusterPatch().dict(**_PATCH_EXPORT),
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = parse_obj_as(ClusterOut, response.json())
    assert returned_cluster.dict() == original_cluster.dict()

    # modify some simple things
    expected_modified_cluster = original_cluster.copy()
    for cluster_patch in [
        ClusterPatch(name=faker.name()),
        ClusterPatch(description=faker.text()),
        ClusterPatch(type=ClusterType.ON_PREMISE),
        ClusterPatch(thumbnail=faker.uri()),
        ClusterPatch(endpoint=faker.uri()),
        ClusterPatch(authentication=cluster_simple_authentication()),
    ]:
        jsonable_cluster_patch = cluster_patch.dict(**_PATCH_EXPORT)
        print(f"--> patching cluster with {jsonable_cluster_patch}")
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
            json=jsonable_cluster_patch,
        )
        assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
        returned_cluster = parse_obj_as(ClusterOut, response.json())
        expected_modified_cluster = expected_modified_cluster.copy(
            update=cluster_patch.dict(**_PATCH_EXPORT)
        )
        assert returned_cluster.dict() == expected_modified_cluster.dict()

    # we can change the access rights, the owner rights are always kept
    user_2 = user_db()

    for rights in [
        CLUSTER_ADMIN_RIGHTS,
        CLUSTER_MANAGER_RIGHTS,
        CLUSTER_USER_RIGHTS,
        CLUSTER_NO_RIGHTS,
    ]:
        cluster_patch = ClusterPatch(accessRights={user_2["primary_gid"]: rights})
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
            json=cluster_patch.dict(**_PATCH_EXPORT),
        )
        assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
        returned_cluster = Cluster.parse_obj(response.json())

        expected_modified_cluster.access_rights[user_2["primary_gid"]] = rights
        assert returned_cluster.dict() == expected_modified_cluster.dict()
    # we can change the owner since we are admin
    cluster_patch = ClusterPatch(owner=user_2["primary_gid"])
    response = await async_client.patch(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
        json=cluster_patch.dict(**_PATCH_EXPORT),
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = Cluster.parse_obj(response.json())
    expected_modified_cluster.owner = user_2["primary_gid"]
    expected_modified_cluster.access_rights[
        user_2["primary_gid"]
    ] = CLUSTER_ADMIN_RIGHTS
    assert returned_cluster.dict() == expected_modified_cluster.dict()

    # we should not be able to reduce the rights of the new owner
    cluster_patch = ClusterPatch(
        accessRights={user_2["primary_gid"]: CLUSTER_NO_RIGHTS}
    )
    response = await async_client.patch(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
        json=cluster_patch.dict(**_PATCH_EXPORT),
    )
    assert (
        response.status_code == status.HTTP_403_FORBIDDEN
    ), f"received {response.text}"


@pytest.mark.parametrize(
    "cluster_sharing_rights, can_use, can_manage, can_administer",
    [
        pytest.param(
            CLUSTER_ADMIN_RIGHTS, True, True, True, id="SHARE_WITH_ADMIN_RIGHTS"
        ),
        pytest.param(
            CLUSTER_MANAGER_RIGHTS, True, True, False, id="SHARE_WITH_MANAGER_RIGHTS"
        ),
        pytest.param(
            CLUSTER_USER_RIGHTS, True, False, False, id="SHARE_WITH_USER_RIGHTS"
        ),
        pytest.param(CLUSTER_NO_RIGHTS, False, False, False, id="DENY_RIGHTS"),
    ],
)
async def test_update_another_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
    cluster_sharing_rights: ClusterAccessRights,
    can_use: bool,
    can_manage: bool,
    can_administer: bool,
):
    """user_1 is the owner and administrator, he/she gives some rights to user 2"""

    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    user_1 = user_db()
    user_2 = user_db()
    # let's create some clusters
    a_bunch_of_clusters = [
        cluster(
            user_1,
            name=f"pytest cluster{n:04}",
            access_rights={
                user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS,
                user_2["primary_gid"]: cluster_sharing_rights,
            },
        )
        for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)
    # get the original one
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    original_cluster = parse_obj_as(ClusterOut, response.json())

    # let's try to modify stuff as we are user 2
    for cluster_patch in [
        ClusterPatch(name=faker.name()),
        ClusterPatch(description=faker.text()),
        ClusterPatch(type=ClusterType.ON_PREMISE),
        ClusterPatch(thumbnail=faker.uri()),
        ClusterPatch(endpoint=faker.uri()),
        ClusterPatch(authentication=cluster_simple_authentication()),
    ]:
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}",
            json=cluster_patch.dict(**_PATCH_EXPORT),
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if can_manage
            else status.HTTP_403_FORBIDDEN
        ), f"received {response.text}"

    # let's try to add/remove someone (reserved to managers)
    user_3 = user_db()
    for rights in [
        CLUSTER_USER_RIGHTS,  # add user
        CLUSTER_NO_RIGHTS,  # remove user
    ]:
        # try to add user 3
        cluster_patch = ClusterPatch(accessRights={user_3["primary_gid"]: rights})
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}",
            json=cluster_patch.dict(**_PATCH_EXPORT),
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if can_manage
            else status.HTTP_403_FORBIDDEN
        ), f"received {response.text} while {'adding' if rights == CLUSTER_USER_RIGHTS else 'removing'} user"

    # modify rights to admin/manager (reserved to administrators)
    for rights in [
        CLUSTER_ADMIN_RIGHTS,
        CLUSTER_MANAGER_RIGHTS,
    ]:
        cluster_patch = ClusterPatch(accessRights={user_3["primary_gid"]: rights})
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}",
            json=cluster_patch.dict(**_PATCH_EXPORT),
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if can_administer
            else status.HTTP_403_FORBIDDEN
        ), f"received {response.text}"


async def test_delete_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
):
    user_1 = user_db()
    # let's create some clusters
    a_bunch_of_clusters = [
        cluster(
            user_1,
            name=f"pytest cluster{n:04}",
            access_rights={
                user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS,
            },
        )
        for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)
    # let's delete that cluster
    response = await async_client.delete(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert (
        response.status_code == status.HTTP_204_NO_CONTENT
    ), f"received {response.text}"
    # now check it is gone
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"received {response.text}"


@pytest.mark.parametrize(
    "cluster_sharing_rights, can_administer",
    [
        pytest.param(CLUSTER_ADMIN_RIGHTS, True, id="SHARE_WITH_ADMIN_RIGHTS"),
        pytest.param(CLUSTER_MANAGER_RIGHTS, False, id="SHARE_WITH_MANAGER_RIGHTS"),
        pytest.param(CLUSTER_USER_RIGHTS, False, id="SHARE_WITH_USER_RIGHTS"),
        pytest.param(CLUSTER_NO_RIGHTS, False, id="DENY_RIGHTS"),
    ],
)
async def test_delete_another_cluster(
    clusters_config: None,
    user_db: Callable[..., Dict],
    cluster: Callable[..., Cluster],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
    cluster_sharing_rights: ClusterAccessRights,
    can_administer: bool,
):
    user_1 = user_db()
    user_2 = user_db()
    # let's create some clusters
    a_bunch_of_clusters = [
        cluster(
            user_1,
            name=f"pytest cluster{n:04}",
            access_rights={
                user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS,
                user_2["primary_gid"]: cluster_sharing_rights,
            },
        )
        for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)
    # let's delete that cluster as user_2
    response = await async_client.delete(
        f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}"
    )
    assert (
        response.status_code == status.HTTP_204_NO_CONTENT
        if can_administer
        else status.HTTP_403_FORBIDDEN
    ), f"received {response.text}"
    # now check it is gone or still around
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
        if can_administer
        else status.HTTP_200_OK
    ), f"received {response.text}"


async def test_get_default_cluster_entrypoint(
    clusters_config: None, async_client: httpx.AsyncClient
):
    # This test checks that the default cluster is accessible
    # the default cluster is the osparc internal cluster available through a dask-scheduler
    response = await async_client.get("/v2/clusters/default")
    assert response.status_code == status.HTTP_200_OK
    default_cluster_out = ClusterDetailsOut.parse_obj(response.json())
    response = await async_client.get(f"/v2/clusters/{0}")
    assert response.status_code == status.HTTP_200_OK
    assert default_cluster_out == ClusterDetailsOut.parse_obj(response.json())


async def test_local_dask_gateway_server(local_dask_gateway_server: DaskGatewayServer):
    async with Gateway(
        local_dask_gateway_server.address,
        local_dask_gateway_server.proxy_address,
        asynchronous=True,
        auth=auth.BasicAuth("pytest_user", local_dask_gateway_server.password),
    ) as gateway:
        print(f"--> {gateway=} created")
        cluster_options = await gateway.cluster_options()
        gateway_versions = await gateway.get_versions()
        clusters_list = await gateway.list_clusters()
        print(f"--> {gateway_versions=}, {cluster_options=}, {clusters_list=}")
        for option in cluster_options.items():
            print(f"--> {option=}")

        async with gateway.new_cluster() as cluster:
            assert cluster
            print(f"--> created new cluster {cluster=}, {cluster.scheduler_info=}")
            NUM_WORKERS = 10
            await cluster.scale(NUM_WORKERS)
            print(f"--> scaling cluster {cluster=} to {NUM_WORKERS} workers")
            async for attempt in AsyncRetrying(
                reraise=True, wait=wait_fixed(0.24), stop=stop_after_delay(30)
            ):
                with attempt:
                    print(
                        f"cluster {cluster=} has now {len(cluster.scheduler_info.get('workers', []))} worker(s)"
                    )
                    assert len(cluster.scheduler_info.get("workers", 0)) == 10

            async with cluster.get_client() as client:
                print(f"--> created new client {client=}, submitting a job")
                res = await client.submit(lambda x: x + 1, 1)  # type: ignore
                assert res == 2

            print(f"--> scaling cluster {cluster=} back to 0")
            await cluster.scale(0)

            async for attempt in AsyncRetrying(
                reraise=True, wait=wait_fixed(0.24), stop=stop_after_delay(30)
            ):
                with attempt:
                    print(
                        f"cluster {cluster=} has now {len(cluster.scheduler_info.get('workers', []))}"
                    )
                    assert len(cluster.scheduler_info.get("workers", 0)) == 0


async def _get_cluster_out(
    async_client: httpx.AsyncClient, cluster_id: NonNegativeInt
) -> ClusterDetailsOut:
    response = await async_client.get(f"/v2/clusters/{cluster_id}")
    assert response.status_code == status.HTTP_200_OK
    print(f"<-- received cluster details response {response=}")
    cluster_out = ClusterDetailsOut.parse_obj(response.json())
    assert cluster_out
    print(f"<-- received cluster details {cluster_out=}")
    assert cluster_out.scheduler, "the cluster's scheduler is not started!"
    return cluster_out


async def test_get_cluster_entrypoint(
    clusters_config: None,
    async_client: httpx.AsyncClient,
    local_dask_gateway_server: DaskGatewayServer,
    cluster: Callable[..., Cluster],
    dask_gateway_cluster: GatewayCluster,
    dask_gateway_cluster_client: DaskClient,
):
    # define the cluster in the DB
    some_cluster = cluster(
        endpoint=local_dask_gateway_server.address,
        authentication=SimpleAuthentication(
            username="pytest_user", password=local_dask_gateway_server.password
        ).dict(by_alias=True),
    )
    # in its present state, the cluster should have no workers
    cluster_out = await _get_cluster_out(async_client, some_cluster.id)
    assert not cluster_out.scheduler.workers, "the cluster should not have any worker!"

    # now let's scale the cluster
    _NUM_WORKERS = 1
    await dask_gateway_cluster.scale(_NUM_WORKERS)
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(60), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_out(async_client, some_cluster.id)
            assert cluster_out.scheduler.workers, "the cluster has no workers!"
            assert (
                len(cluster_out.scheduler.workers) == _NUM_WORKERS
            ), f"the cluster is missing {_NUM_WORKERS}, currently has {len(cluster_out.scheduler.workers)}"
            print(
                f"cluster now has its {_NUM_WORKERS}, after {json.dumps(attempt.retry_state.retry_object.statistics)}"
            )
    print(f"!!> cluster dashboard link: {dask_gateway_cluster.dashboard_link}")

    # let's start some computation
    _TASK_SLEEP_TIME = 5

    def do_some_work(x: int):
        import time

        time.sleep(x)
        return True

    task = dask_gateway_cluster_client.submit(do_some_work, _TASK_SLEEP_TIME)
    # wait for the computation to start, we should see this in the cluster infos
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_out(async_client, some_cluster.id)
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.executing
                == 1
            ), "worker is not executing the task"
            print(
                f"!!> cluster metrics: {next(iter(cluster_out.scheduler.workers.values())).metrics=}"
            )
    # let's wait for the result
    result = task.result(timeout=_TASK_SLEEP_TIME + 5)
    assert result
    assert await result == True
    # wait for the computation to effectively stop
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(20), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_out(async_client, some_cluster.id)
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.executing
                == 0
            ), "worker is still executing the task"
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.in_memory
                == 1
            ), "worker did not keep the result in memory"
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.cpu == 0
            ), "worker did not keep the result in memory"
            print(
                f"!!> cluster metrics: {next(iter(cluster_out.scheduler.workers.values())).metrics=}"
            )

    # since the task is completed the worker should have stopped executing
    cluster_out = await _get_cluster_out(async_client, some_cluster.id)
    worker_data = next(iter(cluster_out.scheduler.workers.values()))
    assert worker_data.metrics.executing == 0
    # in dask, the task remains in memory until the result is deleted
    assert worker_data.metrics.in_memory == 1
