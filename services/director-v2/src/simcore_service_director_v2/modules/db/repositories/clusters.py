import logging
from typing import Dict, Iterable, List, Optional

import sqlalchemy as sa
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_NO_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
    ClusterAccessRights,
)
from models_library.users import UserID
from pydantic.types import PositiveInt
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.users import users

from ....core.errors import ClusterAccessForbidden, ClusterNotFoundError
from ....models.schemas.clusters import ClusterCreate, ClusterPatch
from ....models.schemas.constants import ClusterID
from ._base import BaseRepository

logger = logging.getLogger(__name__)


async def _clusters_from_cluster_ids(
    conn: sa.engine.Connection,
    cluster_ids: Iterable[PositiveInt],
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
            cluster_id_to_cluster[cluster_id] = Cluster(
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


async def _compute_user_access_rights(
    conn: sa.engine.Connection, user_id: UserID, cluster: Cluster
) -> ClusterAccessRights:
    result = await conn.execute(
        sa.select([user_to_groups.c.gid, groups.c.type])
        .where(user_to_groups.c.uid == user_id)
        .order_by(groups.c.type)
        .join(groups)
    )
    user_groups = await result.fetchall()

    # get the primary group first, as it has precedence
    primary_group_row = next(
        filter(lambda ugrp: ugrp[1] == GroupType.PRIMARY, user_groups)
    )
    if primary_grp_rights := cluster.access_rights.get(primary_group_row.gid):
        return primary_grp_rights

    solved_rights = CLUSTER_NO_RIGHTS.dict()
    for group_row in filter(lambda ugrp: ugrp[1] != GroupType.PRIMARY, user_groups):
        grp_access = cluster.access_rights.get(group_row.gid, CLUSTER_NO_RIGHTS).dict()
        for operation in ["read", "write", "delete"]:
            solved_rights[operation] |= grp_access[operation]
    return ClusterAccessRights(**solved_rights)


class ClustersRepository(BaseRepository):
    async def create_cluster(self, user_id, new_cluster: ClusterCreate) -> Cluster:
        async with self.db_engine.acquire() as conn:
            user_primary_gid = await conn.scalar(
                sa.select([users.c.primary_gid]).where(users.c.id == user_id)
            )
            new_cluster.owner = user_primary_gid
            new_cluster_id = await conn.scalar(
                sa.insert(
                    clusters, values=new_cluster.to_clusters_db(only_update=False)
                ).returning(clusters.c.id)
            )
        return await self.get_cluster(user_id, new_cluster_id)

    async def list_clusters(self, user_id: UserID) -> List[Cluster]:
        async with self.db_engine.acquire() as conn:
            result = await conn.execute(
                sa.select([clusters.c.id], distinct=True)
                .where(
                    cluster_to_groups.c.gid.in_(
                        # get the groups of the user where he/she has read access
                        sa.select([groups.c.gid])
                        .where((user_to_groups.c.uid == user_id))
                        .order_by(groups.c.gid)
                        .join(user_to_groups)
                        .cte()
                    )
                    & cluster_to_groups.c.read
                )
                .join(cluster_to_groups)
            )
            cluster_ids = await result.fetchall()
            return await _clusters_from_cluster_ids(conn, {c.id for c in cluster_ids})

    async def get_cluster(self, user_id: UserID, cluster_id: ClusterID) -> Cluster:
        async with self.db_engine.acquire() as conn:
            clusters_list = await _clusters_from_cluster_ids(conn, {cluster_id})
            if not clusters_list:
                raise ClusterNotFoundError(cluster_id=cluster_id)
            the_cluster = clusters_list[0]

            access_rights = await _compute_user_access_rights(
                conn, user_id, the_cluster
            )
            logger.debug(
                "found cluster in DB: %s, with computed %s",
                f"{the_cluster=}",
                f"{access_rights=}",
            )
        if not access_rights.read:
            raise ClusterAccessForbidden(cluster_id=cluster_id)

        return the_cluster

    async def update_cluster(
        self, user_id: UserID, cluster_id: ClusterID, updated_cluster: ClusterPatch
    ) -> Cluster:
        async with self.db_engine.acquire() as conn:
            clusters_list = await _clusters_from_cluster_ids(conn, {cluster_id})
            if not clusters_list:
                raise ClusterNotFoundError(cluster_id=cluster_id)
            the_cluster = clusters_list[0]

            this_user_access_rights = await _compute_user_access_rights(
                conn, user_id, the_cluster
            )
            logger.debug(
                "found cluster in DB: %s, with computed %s",
                f"{the_cluster=}",
                f"{this_user_access_rights=}",
            )

            if not this_user_access_rights.write:
                raise ClusterAccessForbidden(cluster_id=cluster_id)

            if updated_cluster.owner and updated_cluster.owner != the_cluster.owner:
                # if the user wants to change the owner, we need more rights here
                if this_user_access_rights != CLUSTER_ADMIN_RIGHTS:
                    raise ClusterAccessForbidden(cluster_id=cluster_id)

                # ensure the new owner has admin rights, too
                if not updated_cluster.access_rights:
                    updated_cluster.access_rights = {
                        updated_cluster.owner: CLUSTER_ADMIN_RIGHTS
                    }
                else:
                    updated_cluster.access_rights[
                        updated_cluster.owner
                    ] = CLUSTER_ADMIN_RIGHTS

            if (
                updated_cluster.access_rights
                and updated_cluster.access_rights != the_cluster.access_rights
            ):
                # ensure the user is not trying to mess around owner admin rights
                if (
                    updated_cluster.access_rights.setdefault(
                        the_cluster.owner, CLUSTER_ADMIN_RIGHTS
                    )
                    != CLUSTER_ADMIN_RIGHTS
                ):
                    raise ClusterAccessForbidden(cluster_id=cluster_id)

            # if the user is a manager he/she may add/remove users
            if (
                this_user_access_rights == CLUSTER_MANAGER_RIGHTS
                and updated_cluster.access_rights
            ):
                for grp, rights in updated_cluster.access_rights.items():
                    if (grp == primary_group and rights != CLUSTER_MANAGER_RIGHTS) or (
                        grp not in [the_cluster.owner, primary_group]
                        and rights
                        not in [
                            CLUSTER_USER_RIGHTS,
                            CLUSTER_NO_RIGHTS,
                        ]
                    ):
                        raise ClusterAccessForbidden(
                            cluster_id, msg="Administrator rights required."
                        )
