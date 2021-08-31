# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=no-value-for-parameter


import random
from typing import Any, Callable, Coroutine, Dict, Iterable, List

import pytest
import sqlalchemy as sa
from _helpers import ExpectedResponse, standard_role_response
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.users import GroupID
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import NewUser, create_user
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.clusters.models import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
    ClusterAccessRights,
    ClusterCreate,
    ClusterType,
)
from simcore_service_webserver.groups_api import list_user_groups
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.result import ResultProxy, RowProxy
from sqlalchemy.sql.elements import literal_column


@pytest.fixture
def cluster(
    postgres_db: sa.engine.Engine, faker: Faker
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
            }
        )

        result = postgres_db.execute(
            clusters.insert()
            .values(new_cluster.dict(by_alias=True, exclude={"id", "access_rights"}))
            .returning(literal_column("*"))
        )
        cluster_in_db = result.first()
        assert cluster_in_db is not None
        new_cluster_id = cluster_in_db[clusters.c.id]
        list_of_created_cluster_ids.append(new_cluster_id)

        # when a cluster is created, the DB automatically creates the owner access rights
        for gid, access_rights in new_cluster.access_rights.items():
            result = postgres_db.execute(
                insert(cluster_to_groups)
                .values(
                    **{
                        "cluster_id": new_cluster_id,
                        "gid": gid,
                        "read_access": access_rights.read,
                        "write_access": access_rights.write,
                        "delete_access": access_rights.delete,
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
async def second_user(client: TestClient) -> Callable[..., Dict[str, Any]]:
    async with NewUser({"name": "Second User", "role": "USER"}, client.app) as user:
        yield user


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_list_clusters(
    enable_dev_features: None,
    client: TestClient,
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    second_user: Dict[str, Any],
    primary_group: Dict[str, Any],
    all_group: Dict[str, Any],
    cluster: Callable[..., Coroutine[Any, Any, Cluster]],
    expected: ExpectedResponse,
):
    url = client.app.router["list_clusters_handler"].url_for()
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    if error:
        # we are done here
        return
    # there are no clusters yet
    assert data == []

    # create our own cluster
    admin_cluster: Cluster = await cluster(GroupID(primary_group["gid"]))
    # now the listing should retrieve our cluster
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert len(data) == 1
    assert Cluster.parse_obj(data[0]) == admin_cluster

    # we have a second user that creates a few clusters, some are shared with the first user
    another_primary_group, _, _ = await list_user_groups(client.app, second_user["id"])
    a_cluster_that_may_be_managed: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
        {GroupID(primary_group["gid"]): CLUSTER_MANAGER_RIGHTS},
    )

    a_cluster_that_may_be_used: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
        {GroupID(primary_group["gid"]): CLUSTER_USER_RIGHTS},
    )

    a_cluster_that_is_not_shared: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
    )

    a_cluster_that_may_not_be_used: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
        {
            GroupID(all_group["gid"]): CLUSTER_USER_RIGHTS,
            GroupID(primary_group["gid"]): ClusterAccessRights(
                read=False, write=False, delete=False
            ),
        },
    )

    # now listing should retrieve both clusters
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert len(data) == (1 + 2)
    for d in data:
        assert Cluster.parse_obj(d) in [
            admin_cluster,
            a_cluster_that_may_be_managed,
            a_cluster_that_may_be_used,
        ]


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_create_cluster(
    enable_dev_features: None,
    client: TestClient,
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, Any],
    faker: Faker,
    expected: ExpectedResponse,
):
    url = client.app.router["create_cluster_handler"].url_for()
    cluster_data = {"name": faker.name()}
    rsp = await client.post(f"{url}", json=cluster_data)
    data, error = await assert_status(rsp, expected.ok)
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
    assert row[clusters.c.owner] == primary_group["gid"]
    assert (
        Cluster(
            id=row[clusters.c.id],
            name=cluster_data["name"],
            type=row[clusters.c.type],
            owner=primary_group["gid"],
            access_rights={primary_group["gid"]: CLUSTER_ADMIN_RIGHTS},
        )
        == created_cluster
    )

    # cleanup
    postgres_db.execute(clusters.delete().where(clusters.c.id == row[clusters.c.id]))


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_get_cluster(
    enable_dev_features: None,
    client: TestClient,
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    second_user: Dict[str, Any],
    primary_group: Dict[str, Any],
    all_group: Dict[str, Any],
    cluster: Callable[..., Coroutine[Any, Any, Cluster]],
    faker: Faker,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{25}")
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.not_found)
    if error and user_role in [UserRole.ANONYMOUS, UserRole.GUEST]:
        return
    assert data is None
    # create our own cluster
    admin_cluster: Cluster = await cluster(GroupID(primary_group["gid"]))
    # now the listing should retrieve our cluster
    url = client.app.router["get_cluster_handler"].url_for(
        cluster_id=f"{admin_cluster.id}"
    )
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert Cluster.parse_obj(data) == admin_cluster

    # we have a second user that creates a few clusters, some are shared with the first user
    another_primary_group, _, _ = await list_user_groups(client.app, second_user["id"])
    a_cluster_that_may_be_managed: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
        {GroupID(primary_group["gid"]): CLUSTER_MANAGER_RIGHTS},
    )

    a_cluster_that_may_be_used: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
        {GroupID(primary_group["gid"]): CLUSTER_USER_RIGHTS},
    )

    a_cluster_that_is_not_shared: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
    )

    a_cluster_that_may_not_be_used: Cluster = await cluster(
        GroupID(another_primary_group["gid"]),
        {
            GroupID(all_group["gid"]): CLUSTER_USER_RIGHTS,
            GroupID(primary_group["gid"]): ClusterAccessRights(
                read=False, write=False, delete=False
            ),
        },
    )

    # we should have access to that one
    for cl in [a_cluster_that_may_be_managed, a_cluster_that_may_be_used]:
        url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{cl.id}")
        rsp = await client.get(f"{url}")
        data, error = await assert_status(rsp, expected.ok)
        assert Cluster.parse_obj(data) == cl

    # we should not have access to these
    for cl in [a_cluster_that_is_not_shared, a_cluster_that_may_not_be_used]:
        url = client.app.router["get_cluster_handler"].url_for(cluster_id=f"{cl.id}")
        rsp = await client.get(f"{url}")
        data, error = await assert_status(rsp, expected.forbidden)


def test_update_cluster(client: TestClient):
    pass


def test_delete_cluster(client: TestClient):
    pass
