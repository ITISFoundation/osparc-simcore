# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import random
from collections.abc import Callable, Iterator
from typing import Any, Awaitable

import httpx
import pytest
import sqlalchemy as sa
from _dask_helpers import DaskGatewayServer
from common_library.serialization import model_dump_with_secrets
from distributed.deploy.spec import SpecCluster
from faker import Faker
from httpx import URL
from models_library.api_schemas_directorv2.clusters import (
    ClusterCreate,
    ClusterGet,
    ClusterPatch,
    ClusterPing,
)
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_NO_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
    ClusterAccessRights,
    ClusterAuthentication,
    SimpleAuthentication,
)
from pydantic import AnyHttpUrl, SecretStr, TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.clusters import ClusterType, clusters
from starlette import status

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def clusters_config(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    dask_spec_local_cluster: SpecCluster,
    faker: Faker,
):
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


@pytest.fixture
def cluster_simple_authentication(faker: Faker) -> Callable[[], dict[str, Any]]:
    def creator() -> dict[str, Any]:
        simple_auth = {
            "type": "simple",
            "username": faker.user_name(),
            "password": faker.password(),
        }
        assert SimpleAuthentication.model_validate(simple_auth)
        return simple_auth

    return creator


@pytest.fixture
def clusters_cleaner(postgres_db: sa.engine.Engine) -> Iterator:
    yield
    with postgres_db.connect() as conn:
        conn.execute(sa.delete(clusters))


async def test_list_clusters(
    clusters_config: None,
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    async_client: httpx.AsyncClient,
):
    user_1 = registered_user()
    list_clusters_url = URL(f"/v2/clusters?user_id={user_1['id']}")
    # there is no cluster at the moment, the list shall contain the default cluster
    response = await async_client.get(list_clusters_url)
    assert response.status_code == status.HTTP_200_OK
    returned_clusters_list = TypeAdapter(list[ClusterGet]).validate_python(
        response.json()
    )
    assert (
        len(returned_clusters_list) == 1
    ), f"no default cluster in {returned_clusters_list=}"
    assert (
        returned_clusters_list[0].id == 0
    ), "default cluster id is not the one expected"

    # let's create some clusters
    NUM_CLUSTERS = 111
    for n in range(NUM_CLUSTERS):
        await create_cluster(user_1, name=f"pytest cluster{n:04}")

    response = await async_client.get(list_clusters_url)
    assert response.status_code == status.HTTP_200_OK
    returned_clusters_list = TypeAdapter(list[ClusterGet]).validate_python(
        response.json()
    )
    assert (
        len(returned_clusters_list) == NUM_CLUSTERS + 1
    )  # the default cluster comes on top of the NUM_CLUSTERS
    assert (
        returned_clusters_list[0].id == 0
    ), "the first cluster shall be the platform default cluster"

    # now create a second user and check the clusters are not seen by it BUT the default one
    user_2 = registered_user()
    response = await async_client.get(f"/v2/clusters?user_id={user_2['id']}")
    assert response.status_code == status.HTTP_200_OK
    returned_clusters_list = TypeAdapter(list[ClusterGet]).validate_python(
        response.json()
    )
    assert (
        len(returned_clusters_list) == 1
    ), f"no default cluster in {returned_clusters_list=}"
    assert (
        returned_clusters_list[0].id == 0
    ), "default cluster id is not the one expected"

    # let's create a few more clusters owned by user_1 with specific rights
    for rights, name in [
        (CLUSTER_NO_RIGHTS, "no rights"),
        (CLUSTER_USER_RIGHTS, "user rights"),
        (CLUSTER_MANAGER_RIGHTS, "manager rights"),
        (CLUSTER_ADMIN_RIGHTS, "admin rights"),
    ]:
        await create_cluster(
            user_1,  # cluster is owned by user_1
            name=f"cluster with {name}",
            access_rights={
                user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS,
                user_2["primary_gid"]: rights,
            },
        )

    response = await async_client.get(f"/v2/clusters?user_id={user_2['id']}")
    assert response.status_code == status.HTTP_200_OK
    user_2_clusters = TypeAdapter(list[ClusterGet]).validate_python(response.json())
    # we should find 3 clusters + the default cluster
    assert len(user_2_clusters) == 3 + 1
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
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    async_client: httpx.AsyncClient,
):
    user_1 = registered_user()
    # try to get one that does not exist
    response = await async_client.get(
        f"/v2/clusters/15615165165165?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # let's create some clusters
    a_bunch_of_clusters = [
        await create_cluster(user_1, name=f"pytest cluster{n:04}") for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)

    # there is no cluster at the moment, the list is empty
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = ClusterGet.model_validate(response.json())
    assert returned_cluster
    assert the_cluster.model_dump(
        exclude={"authentication"}
    ) == returned_cluster.model_dump(exclude={"authentication"})

    user_2 = registered_user()
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
        a_cluster = await create_cluster(
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


@pytest.mark.parametrize(
    "cluster_sharing_rights, can_use",
    [
        pytest.param(CLUSTER_ADMIN_RIGHTS, True, id="SHARE_WITH_ADMIN_RIGHTS"),
        pytest.param(CLUSTER_MANAGER_RIGHTS, True, id="SHARE_WITH_MANAGER_RIGHTS"),
        pytest.param(CLUSTER_USER_RIGHTS, True, id="SHARE_WITH_USER_RIGHTS"),
        pytest.param(CLUSTER_NO_RIGHTS, False, id="DENY_RIGHTS"),
    ],
)
async def test_get_another_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    async_client: httpx.AsyncClient,
    cluster_sharing_rights: ClusterAccessRights,
    can_use: bool,
):
    user_1 = registered_user()
    user_2 = registered_user()
    # let's create some clusters
    a_bunch_of_clusters = [
        await create_cluster(
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
    # try to get the cluster as user 2
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}"
    )
    assert (
        response.status_code == status.HTTP_200_OK
        if can_use
        else status.HTTP_403_FORBIDDEN
    ), f"received {response.text}"


@pytest.mark.parametrize("with_query", [True, False])
async def test_get_default_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    async_client: httpx.AsyncClient,
    with_query: bool,
):
    user_1 = registered_user()

    get_cluster_url = URL("/v2/clusters/default")
    if with_query:
        get_cluster_url = URL(f"/v2/clusters/default?user_id={user_1['id']}")
    response = await async_client.get(get_cluster_url)
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = ClusterGet.model_validate(response.json())
    assert returned_cluster
    assert returned_cluster.id == 0
    assert returned_cluster.name == "Default cluster"
    assert 1 in returned_cluster.access_rights  # everyone group is always 1
    assert returned_cluster.access_rights[1] == CLUSTER_USER_RIGHTS


async def test_create_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
    postgres_db: sa.engine.Engine,
    clusters_cleaner,
):
    user_1 = registered_user()
    create_cluster_url = URL(f"/v2/clusters?user_id={user_1['id']}")
    cluster_data = ClusterCreate(
        endpoint=faker.uri(),
        authentication=cluster_simple_authentication(),
        name=faker.name(),
        type=random.choice(list(ClusterType)),
        owner=faker.pyint(min_value=1),
    )
    response = await async_client.post(
        create_cluster_url,
        json=model_dump_with_secrets(
            cluster_data,
            show_secrets=True,
            by_alias=True,
            exclude_unset=True,
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, f"received: {response.text}"
    created_cluster = ClusterGet.model_validate(response.json())
    assert created_cluster

    assert cluster_data.model_dump(
        exclude={"id", "owner", "access_rights", "authentication"}
    ) == created_cluster.model_dump(
        exclude={"id", "owner", "access_rights", "authentication"}
    )

    assert created_cluster.id is not None
    assert created_cluster.owner == user_1["primary_gid"]
    assert created_cluster.access_rights == {
        user_1["primary_gid"]: CLUSTER_ADMIN_RIGHTS
    }

    # let's check that DB is correctly setup, there is one entry
    with postgres_db.connect() as conn:
        conn.execute(
            sa.select(clusters).where(clusters.c.name == cluster_data.name)
        ).one()


async def test_update_own_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
):
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    user_1 = registered_user()
    # try to modify one that does not exist
    response = await async_client.patch(
        f"/v2/clusters/15615165165165?user_id={user_1['id']}",
        json=model_dump_with_secrets(
            ClusterPatch(), show_secrets=True, **_PATCH_EXPORT
        ),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # let's create some clusters
    a_bunch_of_clusters = [
        await create_cluster(user_1, name=f"pytest cluster{n:04}") for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)
    # get the original one
    response = await async_client.get(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    original_cluster = ClusterGet.model_validate(response.json())

    # now we modify nothing
    response = await async_client.patch(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
        json=model_dump_with_secrets(
            ClusterPatch(), show_secrets=True, **_PATCH_EXPORT
        ),
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = ClusterGet.model_validate(response.json())
    assert returned_cluster.model_dump() == original_cluster.model_dump()

    # modify some simple things
    expected_modified_cluster = original_cluster.model_copy()
    for cluster_patch in [
        ClusterPatch(name=faker.name()),
        ClusterPatch(description=faker.text()),
        ClusterPatch(type=ClusterType.ON_PREMISE),
        ClusterPatch(thumbnail=faker.uri()),
        ClusterPatch(endpoint=faker.uri()),
        ClusterPatch(authentication=cluster_simple_authentication()),
    ]:
        jsonable_cluster_patch = model_dump_with_secrets(
            cluster_patch, show_secrets=True, **_PATCH_EXPORT
        )
        print(f"--> patching cluster with {jsonable_cluster_patch}")
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
            json=jsonable_cluster_patch,
        )
        assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
        returned_cluster = ClusterGet.model_validate(response.json())
        expected_modified_cluster = expected_modified_cluster.model_copy(
            update=cluster_patch.model_dump(**_PATCH_EXPORT)
        )
        assert returned_cluster.model_dump(
            exclude={"authentication": {"password"}}
        ) == expected_modified_cluster.model_dump(
            exclude={"authentication": {"password"}}
        )

    # we can change the access rights, the owner rights are always kept
    user_2 = registered_user()

    for rights in [
        CLUSTER_ADMIN_RIGHTS,
        CLUSTER_MANAGER_RIGHTS,
        CLUSTER_USER_RIGHTS,
        CLUSTER_NO_RIGHTS,
    ]:
        cluster_patch = ClusterPatch(accessRights={user_2["primary_gid"]: rights})
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
            json=cluster_patch.model_dump(**_PATCH_EXPORT),
        )
        assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
        returned_cluster = ClusterGet.model_validate(response.json())

        expected_modified_cluster.access_rights[user_2["primary_gid"]] = rights
        assert returned_cluster.model_dump(
            exclude={"authentication": {"password"}}
        ) == expected_modified_cluster.model_dump(
            exclude={"authentication": {"password"}}
        )
    # we can change the owner since we are admin
    cluster_patch = ClusterPatch(owner=user_2["primary_gid"])
    response = await async_client.patch(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
        json=model_dump_with_secrets(cluster_patch, show_secrets=True, **_PATCH_EXPORT),
    )
    assert response.status_code == status.HTTP_200_OK, f"received {response.text}"
    returned_cluster = ClusterGet.model_validate(response.json())
    expected_modified_cluster.owner = user_2["primary_gid"]
    expected_modified_cluster.access_rights[
        user_2["primary_gid"]
    ] = CLUSTER_ADMIN_RIGHTS
    assert returned_cluster.model_dump(
        exclude={"authentication": {"password"}}
    ) == expected_modified_cluster.model_dump(exclude={"authentication": {"password"}})

    # we should not be able to reduce the rights of the new owner
    cluster_patch = ClusterPatch(
        accessRights={user_2["primary_gid"]: CLUSTER_NO_RIGHTS}
    )
    response = await async_client.patch(
        f"/v2/clusters/{the_cluster.id}?user_id={user_1['id']}",
        json=model_dump_with_secrets(cluster_patch, show_secrets=True, **_PATCH_EXPORT),
    )
    assert (
        response.status_code == status.HTTP_403_FORBIDDEN
    ), f"received {response.text}"


async def test_update_default_cluster_fails(
    clusters_config: None,
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
):
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    user_1 = registered_user()
    # try to modify one that does not exist
    response = await async_client.patch(
        f"/v2/clusters/default?user_id={user_1['id']}",
        json=model_dump_with_secrets(
            ClusterPatch(), show_secrets=True, **_PATCH_EXPORT
        ),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


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
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
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
    user_1 = registered_user()
    user_2 = registered_user()
    # let's create some clusters
    a_bunch_of_clusters = [
        await create_cluster(
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
    ClusterGet.model_validate(response.json())

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
            json=model_dump_with_secrets(
                cluster_patch, show_secrets=True, **_PATCH_EXPORT
            ),
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if can_manage
            else status.HTTP_403_FORBIDDEN
        ), f"received {response.text}"

    # let's try to add/remove someone (reserved to managers)
    user_3 = registered_user()
    for rights in [
        CLUSTER_USER_RIGHTS,  # add user
        CLUSTER_NO_RIGHTS,  # remove user
    ]:
        # try to add user 3
        cluster_patch = ClusterPatch(accessRights={user_3["primary_gid"]: rights})
        response = await async_client.patch(
            f"/v2/clusters/{the_cluster.id}?user_id={user_2['id']}",
            json=model_dump_with_secrets(
                cluster_patch, show_secrets=True, **_PATCH_EXPORT
            ),
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
            json=model_dump_with_secrets(
                cluster_patch, show_secrets=True, **_PATCH_EXPORT
            ),
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if can_administer
            else status.HTTP_403_FORBIDDEN
        ), f"received {response.text}"


async def test_delete_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    async_client: httpx.AsyncClient,
):
    user_1 = registered_user()
    # let's create some clusters
    a_bunch_of_clusters = [
        await create_cluster(
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
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    cluster_simple_authentication: Callable,
    async_client: httpx.AsyncClient,
    faker: Faker,
    cluster_sharing_rights: ClusterAccessRights,
    can_administer: bool,
):
    user_1 = registered_user()
    user_2 = registered_user()
    # let's create some clusters
    a_bunch_of_clusters = [
        await create_cluster(
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


async def test_delete_default_cluster_fails(
    clusters_config: None,
    registered_user: Callable[..., dict],
    async_client: httpx.AsyncClient,
):
    user_1 = registered_user()
    response = await async_client.delete(f"/v2/clusters/default?user_id={user_1['id']}")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_ping_invalid_cluster_raises_422(
    clusters_config: None,
    async_client: httpx.AsyncClient,
    faker: Faker,
    cluster_simple_authentication: Callable[[], dict[str, Any]],
):
    # calling with wrong data raises
    response = await async_client.post("/v2/clusters:ping", json={})
    with pytest.raises(httpx.HTTPStatusError):
        response.raise_for_status()

    # calling with correct data but non existing cluster also raises
    some_fake_cluster = ClusterPing(
        endpoint=faker.url(),
        authentication=TypeAdapter(ClusterAuthentication).validate_python(
            cluster_simple_authentication()
        ),
    )
    response = await async_client.post(
        "/v2/clusters:ping",
        json=model_dump_with_secrets(
            some_fake_cluster, show_secrets=True, by_alias=True
        ),
    )
    with pytest.raises(httpx.HTTPStatusError):
        response.raise_for_status()


async def test_ping_cluster(
    clusters_config: None,
    async_client: httpx.AsyncClient,
    local_dask_gateway_server: DaskGatewayServer,
):
    valid_cluster = ClusterPing(
        endpoint=TypeAdapter(AnyHttpUrl).validate_python(
            local_dask_gateway_server.address
        ),
        authentication=SimpleAuthentication(
            username="pytest_user",
            password=TypeAdapter(SecretStr).validate_python(
                local_dask_gateway_server.password
            ),
        ),
    )
    response = await async_client.post(
        "/v2/clusters:ping",
        json=model_dump_with_secrets(valid_cluster, show_secrets=True, by_alias=True),
    )
    response.raise_for_status()
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ping_specific_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    create_cluster: Callable[..., Awaitable[Cluster]],
    async_client: httpx.AsyncClient,
    local_dask_gateway_server: DaskGatewayServer,
):
    user_1 = registered_user()
    # try to ping one that does not exist
    response = await async_client.get(
        f"/v2/clusters/15615165165165:ping?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # let's create some clusters and ping one
    a_bunch_of_clusters = [
        await create_cluster(
            user_1,
            name=f"pytest cluster{n:04}",
            endpoint=local_dask_gateway_server.address,
            authentication=SimpleAuthentication(
                username="pytest_user",
                password=TypeAdapter(SecretStr).validate_python(
                    local_dask_gateway_server.password
                ),
            ),
        )
        for n in range(111)
    ]
    the_cluster = random.choice(a_bunch_of_clusters)

    response = await async_client.post(
        f"/v2/clusters/{the_cluster.id}:ping?user_id={user_1['id']}",
    )
    response.raise_for_status()
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ping_default_cluster(
    clusters_config: None,
    registered_user: Callable[..., dict],
    async_client: httpx.AsyncClient,
):
    user_1 = registered_user()
    # try to ping one that does not exist
    response = await async_client.post(
        f"/v2/clusters/default:ping?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
