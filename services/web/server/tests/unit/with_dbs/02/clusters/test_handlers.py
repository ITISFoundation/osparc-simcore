# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements


import json
import random
from typing import Any, AsyncIterable, Callable, Coroutine, Dict, Iterable

import pytest
import sqlalchemy as sa
from _helpers import ExpectedResponse, standard_role_response  # type: ignore
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.users import GroupID
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import NewUser
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.clusters.models import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_NO_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
    ClusterAccessRights,
    ClusterCreate,
    ClusterPatch,
    ClusterType,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.result import ResultProxy
from sqlalchemy.sql.elements import literal_column


@pytest.fixture
def cluster_authentication(faker: Faker) -> Iterable[Callable[[], Dict[str, Any]]]:
    def creator() -> Dict[str, Any]:
        simple_auth = {
            "type": "simple",
            "username": faker.user_name(),
            "password": faker.password(),
        }
        kerberos_auth = {"type": "kerberos"}
        jupyterhub_auth = {"type": "jupyterhub"}
        return random.choice([simple_auth, kerberos_auth, jupyterhub_auth])

    yield creator


@pytest.fixture
def cluster(
    postgres_db: sa.engine.Engine,
    faker: Faker,
    cluster_authentication: Callable[[], Dict[str, Any]],
) -> Iterable[
    Callable[
        [GroupID, Dict[GroupID, ClusterAccessRights]], Coroutine[Any, Any, Cluster]
    ]
]:

    list_of_created_cluster_ids = []

    async def creator(
        gid: GroupID, cluster_access_rights: Dict[GroupID, ClusterAccessRights] = None
    ) -> Cluster:
        new_cluster = ClusterCreate(
            **{
                "name": faker.name(),
                "type": random.choice(list(ClusterType)),
                "owner": gid,
                "access_rights": cluster_access_rights or {},
                "endpoint": faker.uri(),
                "authentication": cluster_authentication(),
            }
        )

        result = postgres_db.execute(
            clusters.insert()
            .values(new_cluster.to_clusters_db(only_update=False))
            .returning(literal_column("*"))
        )
        cluster_in_db = result.first()
        assert cluster_in_db is not None
        new_cluster_id = cluster_in_db[clusters.c.id]
        list_of_created_cluster_ids.append(new_cluster_id)

        # when a cluster is created, the DB automatically creates the owner access rights
        for group_id, access_rights in new_cluster.access_rights.items():
            result = postgres_db.execute(
                insert(cluster_to_groups)
                .values(
                    **{
                        "cluster_id": new_cluster_id,
                        "gid": group_id,
                        "read": access_rights.read,
                        "write": access_rights.write,
                        "delete": access_rights.delete,
                    }
                )
                .on_conflict_do_nothing()
            )

        return Cluster(
            id=new_cluster_id, **new_cluster.dict(by_alias=True, exclude={"id"})
        )

    yield creator

    # clean up
    postgres_db.execute(
        clusters.delete().where(clusters.c.id.in_(list_of_created_cluster_ids))
    )


@pytest.fixture(scope="function")
async def second_user(
    client: TestClient,
) -> AsyncIterable[Dict[str, Any]]:
    async with NewUser({"name": "Second User", "role": "USER"}, client.app) as user:
        yield user


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_clusters(
    enable_dev_features: None,
    client: TestClient,
    logged_user: Dict[str, Any],
    second_user: Dict[str, Any],
    all_group: Dict[str, Any],
    cluster: Callable[..., Coroutine[Any, Any, Cluster]],
    expected: ExpectedResponse,
):
    # check empty clusters
    url = client.app.router["list_clusters_handler"].url_for()
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if error:
        # we are done here, anonymous and guests cannot list
        return
    assert data == []

    # create our own cluster, and check it is listed
    admin_cluster: Cluster = await cluster(GroupID(logged_user["primary_gid"]))
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert len(data) == 1
    assert Cluster.parse_obj(data[0]) == admin_cluster

    # we have a second user that creates a few clusters, some are shared with the first user
    a_cluster_that_may_be_administred: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_MANAGER_RIGHTS},
    )
    a_cluster_that_may_be_managed: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_MANAGER_RIGHTS},
    )

    a_cluster_that_may_be_used: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_USER_RIGHTS},
    )

    a_cluster_that_is_not_shared: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
    )

    a_cluster_that_may_not_be_used: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {
            GroupID(all_group["gid"]): CLUSTER_USER_RIGHTS,
            GroupID(logged_user["primary_gid"]): CLUSTER_NO_RIGHTS,
        },
    )

    # now listing should retrieve both clusters
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert len(data) == (1 + 3)
    for d in data:
        assert Cluster.parse_obj(d) in [
            admin_cluster,
            a_cluster_that_may_be_administred,
            a_cluster_that_may_be_managed,
            a_cluster_that_may_be_used,
        ]


@pytest.mark.parametrize(
    "authentication",
    [
        {"type": "simple", "username": "fake", "password": "sldfkjsl"},
        {"type": "kerberos"},
        {"type": "jupyterhub"},
    ],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_cluster(
    enable_dev_features: None,
    client: TestClient,
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    faker: Faker,
    user_role: UserRole,
    authentication: Dict[str, Any],
    expected: ExpectedResponse,
):
    # check we can create a cluster
    url = client.app.router["create_cluster_handler"].url_for()
    cluster_data = json.loads(
        ClusterCreate(
            endpoint=faker.uri(),
            authentication=authentication,
            name=faker.name(),
            type=random.choice(list(ClusterType)),
        ).json(by_alias=True, exclude_unset=True)
    )
    rsp = await client.post(f"{url}", json=cluster_data)
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

    # check database entry was correctly created
    result: ResultProxy = postgres_db.execute(
        sa.select([clusters]).where(clusters.c.name == cluster_data["name"])
    )
    assert result, "could not find cluster in database"
    row = result.fetchone()
    assert row, "could not find cluster in database"
    assert row[clusters.c.name] == cluster_data["name"]
    assert row[clusters.c.owner] == logged_user["primary_gid"]
    assert (
        Cluster(
            id=row[clusters.c.id],
            name=cluster_data["name"],
            type=row[clusters.c.type],
            endpoint=row[clusters.c.endpoint],
            authentication=row[clusters.c.authentication],
            owner=logged_user["primary_gid"],
            access_rights={logged_user["primary_gid"]: CLUSTER_ADMIN_RIGHTS},
        )
        == created_cluster
    )

    # cleanup
    postgres_db.execute(clusters.delete().where(clusters.c.id == row[clusters.c.id]))


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_get_cluster(
    enable_dev_features: None,
    client: TestClient,
    logged_user: Dict[str, Any],
    second_user: Dict[str, Any],
    all_group: Dict[str, Any],
    cluster: Callable[..., Coroutine[Any, Any, Cluster]],
    user_role: UserRole,
    expected: ExpectedResponse,
):
    # check not found
    url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.not_found)
    if error and user_role in [UserRole.ANONYMOUS, UserRole.GUEST]:
        return
    assert data is None

    # create our own cluster, and we can get it
    admin_cluster: Cluster = await cluster(GroupID(logged_user["primary_gid"]))
    url = client.app.router["get_cluster_handler"].url_for(
        cluster_id=f"{admin_cluster.id}"
    )
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert Cluster.parse_obj(data) == admin_cluster

    # we have a second user that creates a few clusters, some are shared with the first user
    a_cluster_that_may_be_administrated: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_MANAGER_RIGHTS},
    )
    a_cluster_that_may_be_managed: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_MANAGER_RIGHTS},
    )
    a_cluster_that_may_be_used: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_USER_RIGHTS},
    )
    a_cluster_that_is_not_shared: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
    )
    a_cluster_that_may_not_be_used: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {
            GroupID(all_group["gid"]): CLUSTER_USER_RIGHTS,
            GroupID(logged_user["primary_gid"]): CLUSTER_NO_RIGHTS,
        },
    )

    # we should have access to that one
    for cl in [
        a_cluster_that_may_be_administrated,
        a_cluster_that_may_be_managed,
        a_cluster_that_may_be_used,
    ]:
        url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{cl.id}")
        rsp = await client.get(f"{url}")
        data, error = await assert_status(rsp, expected.ok)
        assert Cluster.parse_obj(data) == cl

    # we should not have access to these
    for cl in [a_cluster_that_is_not_shared, a_cluster_that_may_not_be_used]:
        url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{cl.id}")
        rsp = await client.get(f"{url}")
        data, error = await assert_status(rsp, expected.forbidden)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_update_cluster(
    enable_dev_features: None,
    client: TestClient,
    logged_user: Dict[str, Any],
    second_user: Dict[str, Any],
    all_group: Dict[str, Any],
    cluster: Callable[..., Coroutine[Any, Any, Cluster]],
    user_role: UserRole,
    expected: ExpectedResponse,
    cluster_authentication: Callable[[], Dict[str, Any]],
):
    _PATCH_EXPORT = {"by_alias": True, "exclude_unset": True, "exclude_none": True}
    # check modifying invalid returns not found
    url = client.app.router["update_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.patch(
        f"{url}",
        json=ClusterPatch().dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.not_found)
    if error and user_role in [UserRole.ANONYMOUS, UserRole.GUEST]:
        return

    # create our own cluster, allows us to modify it
    admin_cluster: Cluster = await cluster(GroupID(logged_user["primary_gid"]))
    url = client.app.router["update_cluster_handler"].url_for(
        cluster_id=f"{admin_cluster.id}"
    )
    # we can modify these simple things
    expected_admin_cluster = admin_cluster.copy()
    for cluster_patch in [
        ClusterPatch(name="My patched cluster name"),
        ClusterPatch(description="My patched cluster description"),
        ClusterPatch(type=ClusterType.ON_PREMISE),
        ClusterPatch(thumbnail="https://placeimg.com/640/480/nature"),
        ClusterPatch(endpoint="https://some_other_endpoint.com"),
        ClusterPatch(authentication=cluster_authentication()),
    ]:
        jsonable_cluster_patch = json.loads(cluster_patch.json(**_PATCH_EXPORT))
        rsp = await client.patch(f"{url}", json=jsonable_cluster_patch)
        data, error = await assert_status(rsp, expected.ok)
        expected_admin_cluster = expected_admin_cluster.copy(
            update=cluster_patch.dict(**_PATCH_EXPORT)
        )
        assert Cluster.parse_obj(data) == expected_admin_cluster

    # we can change the access rights, the owner rights are always kept
    for rights in [
        CLUSTER_ADMIN_RIGHTS,
        CLUSTER_MANAGER_RIGHTS,
        CLUSTER_USER_RIGHTS,
        CLUSTER_NO_RIGHTS,
    ]:
        cluster_patch = ClusterPatch(accessRights={second_user["primary_gid"]: rights})
        rsp = await client.patch(
            f"{url}",
            json=cluster_patch.dict(**_PATCH_EXPORT),
        )
        data, error = await assert_status(rsp, expected.ok)
        expected_admin_cluster.access_rights[second_user["primary_gid"]] = rights
        assert Cluster.parse_obj(data) == expected_admin_cluster

    # we can change the owner since we are admin
    cluster_patch = ClusterPatch(owner=second_user["primary_gid"])
    rsp = await client.patch(
        f"{url}",
        json=cluster_patch.dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.ok)
    expected_admin_cluster.owner = second_user["primary_gid"]
    expected_admin_cluster.access_rights[
        second_user["primary_gid"]
    ] = CLUSTER_ADMIN_RIGHTS
    assert Cluster.parse_obj(data) == expected_admin_cluster

    # we should not be able to reduce the rights of the new owner
    cluster_patch = ClusterPatch(
        accessRights={second_user["primary_gid"]: CLUSTER_NO_RIGHTS}
    )
    rsp = await client.patch(
        f"{url}",
        json=cluster_patch.dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.forbidden)

    # we have a second user that creates a few clusters, some are shared with the first user
    a_cluster_that_may_be_administrated: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_ADMIN_RIGHTS},
    )
    a_cluster_that_may_be_managed: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_MANAGER_RIGHTS},
    )
    a_cluster_that_may_be_used: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {GroupID(logged_user["primary_gid"]): CLUSTER_USER_RIGHTS},
    )
    a_cluster_that_is_not_shared: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
    )
    a_cluster_that_may_not_be_used: Cluster = await cluster(
        GroupID(second_user["primary_gid"]),
        {
            GroupID(all_group["gid"]): CLUSTER_ADMIN_RIGHTS,
            GroupID(logged_user["primary_gid"]): CLUSTER_NO_RIGHTS,
        },
    )
    # we can manage so we shall be ok here changing the name
    for cl in [a_cluster_that_may_be_administrated, a_cluster_that_may_be_managed]:
        url = client.app.router["update_cluster_handler"].url_for(cluster_id=f"{cl.id}")
        rsp = await client.patch(
            f"{url}",
            json=ClusterPatch(name="I prefer this new name here").dict(**_PATCH_EXPORT),
        )
        data, error = await assert_status(rsp, expected.ok)

    # we can NOT change the owner of this one
    url = client.app.router["update_cluster_handler"].url_for(
        cluster_id=f"{a_cluster_that_may_be_managed.id}"
    )
    rsp = await client.patch(
        f"{url}",
        json=ClusterPatch(owner=logged_user["primary_gid"]).dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.forbidden)

    # we can NOT change ourself to become an admin
    url = client.app.router["update_cluster_handler"].url_for(
        cluster_id=f"{a_cluster_that_may_be_managed.id}"
    )
    rsp = await client.patch(
        f"{url}",
        json=ClusterPatch(
            accessRights={logged_user["primary_gid"]: CLUSTER_ADMIN_RIGHTS}
        ).dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.forbidden)

    # but I can add a user
    url = client.app.router["update_cluster_handler"].url_for(
        cluster_id=f"{a_cluster_that_may_be_managed.id}"
    )
    rsp = await client.patch(
        f"{url}",
        json=ClusterPatch(
            accessRights={
                **a_cluster_that_may_be_managed.access_rights,
                **{
                    logged_user["primary_gid"]: CLUSTER_MANAGER_RIGHTS,
                    all_group["gid"]: CLUSTER_USER_RIGHTS,
                },
            },
        ).dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.ok)

    # and I shall be able to deny a user
    url = client.app.router["update_cluster_handler"].url_for(
        cluster_id=f"{a_cluster_that_may_be_managed.id}"
    )
    rsp = await client.patch(
        f"{url}",
        json=ClusterPatch(
            accessRights={
                logged_user["primary_gid"]: CLUSTER_MANAGER_RIGHTS,
                all_group["gid"]: CLUSTER_NO_RIGHTS,
            }
        ).dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.ok)

    # and I shall be able to remove a user (provided that is not the owner)
    url = client.app.router["update_cluster_handler"].url_for(
        cluster_id=f"{a_cluster_that_may_be_managed.id}"
    )
    rsp = await client.patch(
        f"{url}",
        json=ClusterPatch(
            accessRights={
                logged_user["primary_gid"]: CLUSTER_MANAGER_RIGHTS,
            }
        ).dict(**_PATCH_EXPORT),
    )
    data, error = await assert_status(rsp, expected.ok)

    # but I canNOT add a manager or an admin
    for rights in [CLUSTER_ADMIN_RIGHTS, CLUSTER_MANAGER_RIGHTS]:
        url = client.app.router["update_cluster_handler"].url_for(
            cluster_id=f"{a_cluster_that_may_be_managed.id}"
        )
        rsp = await client.patch(
            f"{url}",
            json=ClusterPatch(accessRights={all_group["gid"]: rights}).dict(
                **_PATCH_EXPORT
            ),
        )
        data, error = await assert_status(rsp, expected.forbidden)

    # we can NOT manage so we shall be forbidden changing the name
    for cl in [
        a_cluster_that_may_be_used,
        a_cluster_that_may_not_be_used,
        a_cluster_that_is_not_shared,
    ]:
        url = client.app.router["update_cluster_handler"].url_for(cluster_id=f"{cl.id}")
        rsp = await client.patch(
            f"{url}",
            json=ClusterPatch(
                name="I prefer this new name here, but I am not allowed"
            ).dict(**_PATCH_EXPORT),
        )
        data, error = await assert_status(rsp, expected.forbidden)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_delete_cluster(
    enable_dev_features: None,
    client: TestClient,
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    second_user: Dict[str, Any],
    cluster: Callable[..., Coroutine[Any, Any, Cluster]],
    faker: Faker,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    # deleting a non-existing cluster returns not found
    url = client.app.router["delete_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.delete(f"{url}")
    data, error = await assert_status(rsp, expected.not_found)
    if error and user_role in [UserRole.ANONYMOUS, UserRole.GUEST]:
        return
    assert data is None

    # create our own cluster allows us to delete it
    admin_cluster: Cluster = await cluster(GroupID(logged_user["primary_gid"]))
    url = client.app.router["delete_cluster_handler"].url_for(
        cluster_id=f"{admin_cluster.id}"
    )
    rsp = await client.delete(f"{url}")
    data, error = await assert_status(rsp, expected.no_content)
    assert data is None

    # check it was deleted
    result: ResultProxy = postgres_db.execute(
        sa.select([clusters]).where(clusters.c.id == admin_cluster.id)
    )
    assert result.rowcount == 0
