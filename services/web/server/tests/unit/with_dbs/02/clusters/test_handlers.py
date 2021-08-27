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
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_service_webserver.clusters.models import (
    CLUSTER_ADMIN_RIGHTS,
    Cluster,
    ClusterType,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.elements import literal_column


@pytest.fixture
def cluster(
    postgres_db: sa.engine.Engine, faker: Faker
) -> Iterable[Callable[[GroupID], Coroutine[Any, Any, Cluster]]]:

    list_of_created_cluster_ids = []

    async def creator(gid: GroupID) -> Cluster:
        new_cluster = Cluster(
            **{
                "name": faker.name(),
                "type": random.choice(list(ClusterType)),
                "owner": gid,
                "access_rights": {gid: CLUSTER_ADMIN_RIGHTS},
            }
        )

        result = postgres_db.execute(
            clusters.insert()
            .values(new_cluster.dict(by_alias=True, exclude={"access_rights"}))
            .returning(literal_column("*"))
        )
        cluster_in_db = result.first()
        assert cluster_in_db is not None
        new_cluster_id = cluster_in_db[clusters.c.id]
        list_of_created_cluster_ids.append(new_cluster_id)

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

        return new_cluster

    yield creator

    # clean up
    postgres_db.execute(
        clusters.delete().where(clusters.c.id.in_(list_of_created_cluster_ids))
    )


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_list_clusters(
    enable_dev_features: None,
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    all_group: Dict[str, str],
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

    # create a cluster
    new_cluster: Cluster = await cluster(GroupID(primary_group["gid"]))

    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)
    assert len(data) == 1


def test_create_cluster(client: TestClient):
    pass


def test_get_cluster(client: TestClient):
    pass


def test_update_cluster(client: TestClient):
    pass


def test_delete_cluster(client: TestClient):
    pass
