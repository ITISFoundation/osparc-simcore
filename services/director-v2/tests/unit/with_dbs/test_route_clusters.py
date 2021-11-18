# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Callable, Dict, Iterable, List

import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from models_library.clusters import Cluster
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from starlette import status
from starlette.testclient import TestClient

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture()
def clusters_config(
    mock_env: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    monkeypatch: MonkeyPatch,
):
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")


@pytest.fixture
def cluster(
    user_db: Dict,
    postgres_db: sa.engine.Engine,
) -> Iterable[Callable[..., Cluster]]:
    created_cluster_ids: List[str] = []

    def creator(**overrides) -> Cluster:
        cluster_config = Cluster.Config.schema_extra["examples"][0]
        cluster_config["owner"] = user_db["primary_gid"]
        cluster_config.update(**overrides)
        new_cluster = Cluster.parse_obj(cluster_config)
        assert new_cluster

        with postgres_db.connect() as conn:
            created_cluser_id = conn.scalar(
                # pylint: disable=no-value-for-parameter
                clusters.insert()
                .values(new_cluster.to_clusters_db(only_update=False))
                .returning(clusters.c.id)
            )
            result = conn.execute(
                sa.select(
                    [
                        clusters,
                        cluster_to_groups.c.gid,
                        cluster_to_groups.c.read,
                        cluster_to_groups.c.write,
                        cluster_to_groups.c.delete,
                    ]
                )
                .select_from(
                    clusters.join(
                        cluster_to_groups,
                        clusters.c.id == cluster_to_groups.c.cluster_id,
                    )
                )
                .where(clusters.c.id == created_cluser_id)
            )

            row = result.fetchone()
            assert row
            return Cluster.construct(
                id=row[clusters.c.id],
                name=row[clusters.c.name],
                description=row[clusters.c.description],
                type=row[clusters.c.type],
                owner=row[clusters.c.owner],
                endpoint=row[clusters.c.endpoint],
                authentication=row[clusters.c.authentication],
                access_rights={
                    row[clusters.c.owner]: {
                        "read": row[cluster_to_groups.c.read],
                        "write": row[cluster_to_groups.c.write],
                        "delete": row[cluster_to_groups.c.delete],
                    }
                },
            )

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            # pylint: disable=no-value-for-parameter
            clusters.delete().where(clusters.c.project_id.in_(created_cluster_ids))
        )


def test_get_cluster_entrypoint(
    clusters_config: None, client: TestClient, cluster: Callable[..., Cluster]
):
    some_cluster = cluster()
    response = client.get(f"/v2/clusters/{some_cluster.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
