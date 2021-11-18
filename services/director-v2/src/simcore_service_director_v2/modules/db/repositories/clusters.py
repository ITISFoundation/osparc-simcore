import logging
from typing import Dict, List, Optional, Set

import sqlalchemy as sa
from models_library.clusters import Cluster, ClusterAccessRights
from pydantic.types import PositiveInt
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters

from ....core.errors import ClusterNotFoundError
from ._base import BaseRepository

logger = logging.getLogger(__name__)


async def _clusters_from_cluster_ids(
    conn: sa.engine.Connection,
    cluster_ids: Set[PositiveInt],
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[Cluster]:
    cluster_id_to_cluster: Dict[PositiveInt, Cluster] = {}
    async for row in conn.execute(
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
        .where(clusters.c.id.in_(cluster_ids))
        .offset(offset)
        .limit(limit)
    ):
        cluster_access_rights = {
            row[cluster_to_groups.c.gid]: ClusterAccessRights(
                **{
                    "read": row[cluster_to_groups.c.read],
                    "write": row[cluster_to_groups.c.write],
                    "delete": row[cluster_to_groups.c.delete],
                }
            )
        }

        cluster_id = row[clusters.c.id]
        if cluster_id not in cluster_id_to_cluster:
            cluster_id_to_cluster[cluster_id] = Cluster.construct(
                id=cluster_id,
                name=row[clusters.c.name],
                description=row[clusters.c.description],
                type=row[clusters.c.type],
                owner=row[clusters.c.owner],
                endpoint=row[clusters.c.endpoint],
                authentication=row[clusters.c.authentication],
                thumbnail=row[clusters.c.thumbnail],
                access_rights=cluster_access_rights,
            )
        else:
            cluster_id_to_cluster[cluster_id].access_rights.update(
                cluster_access_rights
            )

    return list(cluster_id_to_cluster.values())


class ClustersRepository(BaseRepository):
    async def get_cluster(self, cluster_id: PositiveInt) -> Cluster:
        async with self.db_engine.acquire() as conn:
            clusters_list = await _clusters_from_cluster_ids(conn, {cluster_id})
            if not clusters_list:
                raise ClusterNotFoundError
            return clusters_list[0]
