from collections import defaultdict
from typing import Dict, List, Optional

import sqlalchemy as sa
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.users import GroupID
from pydantic.types import PositiveInt
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters

from ..db_base_repository import BaseRepository
from .models import Cluster


class ClustersRepository(BaseRepository):
    async def list_clusters_for_groups(
        self, gids: List[GroupID], offset: int = 0, limit: Optional[int] = None
    ) -> List[Cluster]:
        cluster_id_to_cluster: Dict[PositiveInt, Cluster] = {}
        async with self.engine.acquire() as conn:
            async for row in conn.execute(
                sa.select(
                    [
                        clusters,
                        cluster_to_groups.c.gid,
                        cluster_to_groups.c.read_access,
                        cluster_to_groups.c.write_access,
                        cluster_to_groups.c.delete_access,
                    ]
                )
                .select_from(
                    clusters.join(
                        cluster_to_groups,
                        clusters.c.id == cluster_to_groups.c.cluster_id,
                    )
                )
                .where(cluster_to_groups.c.gid.in_(gids))
                .offset(offset)
                .limit(limit)
            ):
                cluster_access_rights = {
                    row[cluster_to_groups.c.gid]: {
                        "read": row[cluster_to_groups.c.read_access],
                        "write": row[cluster_to_groups.c.write_access],
                        "delete": row[cluster_to_groups.c.delete_access],
                    }
                }
                cluster_id = row[clusters.c.id]
                if cluster_id not in cluster_id_to_cluster:
                    cluster_id_to_cluster[cluster_id] = Cluster(
                        name=row[clusters.c.name],
                        description=row[clusters.c.description],
                        type=row[clusters.c.type],
                        owner=row[clusters.c.owner],
                        access_rights=cluster_access_rights,
                    )
                else:
                    cluster_id_to_cluster[cluster_id].access_rights.update(
                        cluster_access_rights
                    )

        return list(cluster_id_to_cluster.values())
