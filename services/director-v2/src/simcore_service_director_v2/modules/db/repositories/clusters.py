import logging
from collections.abc import Iterable

import psycopg2
import sqlalchemy as sa
from aiopg.sa import connection
from models_library.api_schemas_directorv2.clusters import ClusterCreate, ClusterPatch
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_NO_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
    ClusterAccessRights,
    ClusterID,
)
from models_library.users import UserID
from pydantic.types import PositiveInt
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.users import users
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ....core.errors import (
    ClusterAccessForbiddenError,
    ClusterInvalidOperationError,
    ClusterNotFoundError,
)
from ....utils.db import to_clusters_db
from ._base import BaseRepository

logger = logging.getLogger(__name__)


async def _clusters_from_cluster_ids(
    conn: connection.SAConnection,
    cluster_ids: Iterable[PositiveInt],
    offset: int = 0,
    limit: int | None = None,
) -> list[Cluster]:
    cluster_id_to_cluster: dict[PositiveInt, Cluster] = {}
    async for row in conn.execute(
        sa.select(
            clusters,
            cluster_to_groups.c.gid,
            cluster_to_groups.c.read,
            cluster_to_groups.c.write,
            cluster_to_groups.c.delete,
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
    conn: connection.SAConnection, user_id: UserID, cluster: Cluster
) -> ClusterAccessRights:
    result = await conn.execute(
        sa.select(user_to_groups.c.gid, groups.c.type)
        .where(user_to_groups.c.uid == user_id)
        .order_by(groups.c.type)
        .join(groups)
    )
    user_groups = await result.fetchall()
    assert user_groups  # nosec
    # get the primary group first, as it has precedence
    if (
        primary_group_row := next(
            filter(lambda ugrp: ugrp[1] == GroupType.PRIMARY, user_groups), None
        )
    ) and (primary_grp_rights := cluster.access_rights.get(primary_group_row.gid)):
        return primary_grp_rights

    solved_rights = CLUSTER_NO_RIGHTS.model_dump()
    for group_row in filter(lambda ugrp: ugrp[1] != GroupType.PRIMARY, user_groups):
        grp_access = cluster.access_rights.get(group_row.gid, CLUSTER_NO_RIGHTS).model_dump()
        for operation in ["read", "write", "delete"]:
            solved_rights[operation] |= grp_access[operation]
    return ClusterAccessRights(**solved_rights)


class ClustersRepository(BaseRepository):
    async def create_cluster(self, user_id, new_cluster: ClusterCreate) -> Cluster:
        async with self.db_engine.acquire() as conn:
            user_primary_gid = await conn.scalar(
                sa.select(users.c.primary_gid).where(users.c.id == user_id)
            )
            new_cluster.owner = user_primary_gid
            new_cluster_id = await conn.scalar(
                sa.insert(
                    clusters, values=to_clusters_db(new_cluster, only_update=False)
                ).returning(clusters.c.id)
            )
        assert new_cluster_id  # nosec
        return await self.get_cluster(user_id, new_cluster_id)

    async def list_clusters(self, user_id: UserID) -> list[Cluster]:
        async with self.db_engine.acquire() as conn:
            result = await conn.execute(
                sa.select(clusters.c.id)
                .distinct()
                .where(
                    cluster_to_groups.c.gid.in_(
                        # get the groups of the user where he/she has read access
                        sa.select(groups.c.gid)
                        .where(user_to_groups.c.uid == user_id)
                        .order_by(groups.c.gid)
                        .select_from(groups.join(user_to_groups))
                    )
                    & cluster_to_groups.c.read
                )
                .join(cluster_to_groups)
            )
            retrieved_clusters = []
            if cluster_ids := await result.fetchall():
                retrieved_clusters = await _clusters_from_cluster_ids(
                    conn, {c.id for c in cluster_ids}
                )
            return retrieved_clusters

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
            raise ClusterAccessForbiddenError(cluster_id=cluster_id)

        return the_cluster

    async def update_cluster(  # pylint: disable=too-many-branches
        self, user_id: UserID, cluster_id: ClusterID, updated_cluster: ClusterPatch
    ) -> Cluster:
        async with self.db_engine.acquire() as conn:
            clusters_list: list[Cluster] = await _clusters_from_cluster_ids(
                conn, {cluster_id}
            )
            if len(clusters_list) != 1:
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
                raise ClusterAccessForbiddenError(cluster_id=cluster_id)

            if updated_cluster.owner and updated_cluster.owner != the_cluster.owner:
                # if the user wants to change the owner, we need more rights here
                if this_user_access_rights != CLUSTER_ADMIN_RIGHTS:
                    raise ClusterAccessForbiddenError(cluster_id=cluster_id)

                # ensure the new owner has admin rights, too
                if not updated_cluster.access_rights:
                    updated_cluster.access_rights = {
                        updated_cluster.owner: CLUSTER_ADMIN_RIGHTS
                    }
                else:
                    updated_cluster.access_rights[
                        updated_cluster.owner
                    ] = CLUSTER_ADMIN_RIGHTS

            # resolve access rights changes
            resolved_access_rights = the_cluster.access_rights
            if updated_cluster.access_rights:
                # if the user is a manager he/she may ONLY add/remove users
                if this_user_access_rights == CLUSTER_MANAGER_RIGHTS:
                    for grp, rights in updated_cluster.access_rights.items():
                        if grp == the_cluster.owner or rights not in [
                            CLUSTER_USER_RIGHTS,
                            CLUSTER_NO_RIGHTS,
                        ]:
                            # a manager cannot change the owner abilities or create
                            # managers/admins
                            raise ClusterAccessForbiddenError(cluster_id=cluster_id)

                resolved_access_rights.update(updated_cluster.access_rights)
                # ensure the user is not trying to mess around owner admin rights
                if (
                    resolved_access_rights.setdefault(
                        the_cluster.owner, CLUSTER_ADMIN_RIGHTS
                    )
                    != CLUSTER_ADMIN_RIGHTS
                ):
                    raise ClusterAccessForbiddenError(cluster_id=cluster_id)

            # ok we can update now
            try:
                await conn.execute(
                    sa.update(clusters)
                    .where(clusters.c.id == the_cluster.id)
                    .values(to_clusters_db(updated_cluster, only_update=True))
                )
            except psycopg2.DatabaseError as e:
                raise ClusterInvalidOperationError(cluster_id=cluster_id) from e
            # upsert the rights
            if updated_cluster.access_rights:
                for grp, rights in resolved_access_rights.items():
                    insert_stmt = pg_insert(cluster_to_groups).values(
                        **rights.model_dump(by_alias=True), gid=grp, cluster_id=the_cluster.id
                    )
                    on_update_stmt = insert_stmt.on_conflict_do_update(
                        index_elements=[
                            cluster_to_groups.c.cluster_id,
                            cluster_to_groups.c.gid,
                        ],
                        set_=rights.model_dump(by_alias=True),
                    )
                    await conn.execute(on_update_stmt)

            clusters_list = await _clusters_from_cluster_ids(conn, {cluster_id})
            if not clusters_list:
                raise ClusterNotFoundError(cluster_id=cluster_id)
            return clusters_list[0]

    async def delete_cluster(self, user_id: UserID, cluster_id: ClusterID) -> None:
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
            if not access_rights.delete:
                raise ClusterAccessForbiddenError(cluster_id=cluster_id)
            await conn.execute(sa.delete(clusters).where(clusters.c.id == cluster_id))
