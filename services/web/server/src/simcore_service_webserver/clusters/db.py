from typing import Dict, List, Optional, Set

import sqlalchemy as sa
from aiopg.sa.result import ResultProxy
from models_library.users import GroupID
from pydantic.types import PositiveInt
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine.result import RowProxy
from sqlalchemy.sql.elements import literal_column

from ..db_base_repository import BaseRepository
from .exceptions import ClusterAccessForbidden, ClusterNotFoundError
from .models import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_NO_RIGHTS,
    Cluster,
    ClusterAccessRights,
    ClusterCreate,
    ClusterPatch,
)

# Cluster access rights:
# All group comes first, then standard groups, then primary group


def compute_cluster_access_rights(
    cluster: Cluster,
    primary_group: GroupID,
    standard_groups: List[GroupID],
    all_group: GroupID,
) -> ClusterAccessRights:
    # primary access dominates all others
    if primary_grp_rights := cluster.access_rights.get(primary_group):
        return primary_grp_rights

    # solve access by checking all group first, then composing using standard groups
    solved_rights = cluster.access_rights.get(all_group, CLUSTER_NO_RIGHTS).dict()
    for grp in standard_groups:
        grp_access = cluster.access_rights.get(grp, CLUSTER_NO_RIGHTS).dict()
        for operation in ["read", "write", "delete"]:
            solved_rights[operation] |= grp_access[operation]
    return ClusterAccessRights(**solved_rights)


class ClustersRepository(BaseRepository):
    async def _clusters_from_cluster_ids(
        self,
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
            .where(clusters.c.id.in_(cluster_ids))
            .offset(offset)
            .limit(limit)
        ):
            cluster_access_rights = {
                row[cluster_to_groups.c.gid]: ClusterAccessRights(
                    **{
                        "read": row[cluster_to_groups.c.read_access],
                        "write": row[cluster_to_groups.c.write_access],
                        "delete": row[cluster_to_groups.c.delete_access],
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
                    access_rights=cluster_access_rights,
                )
            else:
                cluster_id_to_cluster[cluster_id].access_rights.update(
                    cluster_access_rights
                )

        return list(cluster_id_to_cluster.values())

    async def list_clusters(
        self,
        primary_group: GroupID,
        standard_groups: List[GroupID],
        all_group: GroupID,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Cluster]:
        async with self.engine.acquire() as conn:
            # let's first find which clusters are available for our user
            result: ResultProxy = await conn.execute(
                sa.select([cluster_to_groups.c.cluster_id]).where(
                    cluster_to_groups.c.gid.in_(
                        [all_group, *standard_groups, primary_group]
                    )
                    & (
                        cluster_to_groups.c.read_access
                        | cluster_to_groups.c.write_access
                        | cluster_to_groups.c.delete_access
                    )
                )
            )

            if result is None:
                return []

            cluster_ids: Set[PositiveInt] = {
                r[cluster_to_groups.c.cluster_id] for r in await result.fetchall()
            }

            if not cluster_ids:
                return []

            list_of_clusters = await self._clusters_from_cluster_ids(
                conn, cluster_ids, offset, limit
            )

        def solve_access_rights(
            cluster: Cluster,
            primary_group: GroupID,
        ) -> bool:
            if primary_group_access_rights := cluster.access_rights.get(
                primary_group, None
            ):
                if (primary_group != cluster.owner) and (
                    primary_group_access_rights == CLUSTER_NO_RIGHTS
                ):
                    return False
            return True

        return list(
            filter(
                lambda cluster: solve_access_rights(cluster, primary_group),
                list_of_clusters,
            )
        )

    async def create_cluster(self, new_cluster: ClusterCreate) -> Cluster:
        async with self.engine.acquire() as conn:
            created_cluser_id: int = await conn.scalar(
                # pylint: disable=no-value-for-parameter
                clusters.insert()
                .values(
                    new_cluster.dict(by_alias=True, exclude={"id", "access_rights"})
                )
                .returning(clusters.c.id)
            )

            result = await conn.execute(
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
                .where(clusters.c.id == created_cluser_id)
            )

            row = await result.fetchone()

            assert row  # nosec

            return Cluster.construct(
                id=row[clusters.c.id],
                name=row[clusters.c.name],
                description=row[clusters.c.description],
                type=row[clusters.c.type],
                owner=row[clusters.c.owner],
                access_rights={
                    row[clusters.c.owner]: {
                        "read": row[cluster_to_groups.c.read_access],
                        "write": row[cluster_to_groups.c.write_access],
                        "delete": row[cluster_to_groups.c.delete_access],
                    }
                },
            )

    async def get_cluster(
        self,
        primary_group: GroupID,
        standard_groups: List[GroupID],
        all_group: GroupID,
        cluster_id: PositiveInt,
    ) -> Cluster:
        async with self.engine.acquire() as conn:
            clusters_list: List[Cluster] = await self._clusters_from_cluster_ids(
                conn, {cluster_id}
            )
        if not clusters_list:
            raise ClusterNotFoundError(cluster_id)

        the_cluster = clusters_list[0]
        if not compute_cluster_access_rights(
            the_cluster, primary_group, standard_groups, all_group
        ).read:
            raise ClusterAccessForbidden(cluster_id)

        return the_cluster

    async def update_cluster(
        self,
        primary_group: GroupID,
        standard_groups: List[GroupID],
        all_group: GroupID,
        cluster_id: PositiveInt,
        updated_cluster: ClusterPatch,
    ) -> Cluster:
        async with self.engine.acquire() as conn:
            clusters_list: List[Cluster] = await self._clusters_from_cluster_ids(
                conn, {cluster_id}
            )
            if not clusters_list:
                raise ClusterNotFoundError(cluster_id)
            the_cluster = clusters_list[0]

            this_user_cluster_access_rights = compute_cluster_access_rights(
                the_cluster, primary_group, standard_groups, all_group
            )

            # check that minimal access right necessary to change anything
            if not this_user_cluster_access_rights.write:
                raise ClusterAccessForbidden(cluster_id)

            if updated_cluster.owner and updated_cluster.owner != the_cluster.owner:
                # the user wants to change the owner here, admin rights needed
                if this_user_cluster_access_rights != CLUSTER_ADMIN_RIGHTS:
                    raise ClusterAccessForbidden(cluster_id)

                if not updated_cluster.access_rights:
                    updated_cluster.access_rights = {
                        updated_cluster.owner: CLUSTER_ADMIN_RIGHTS
                    }
                else:
                    updated_cluster.access_rights[
                        updated_cluster.owner
                    ] = CLUSTER_ADMIN_RIGHTS

            # ok we can update now
            await conn.execute(
                sa.update(clusters)
                .where(clusters.c.id == the_cluster.id)
                .values(
                    updated_cluster.dict(
                        by_alias=True,
                        exclude_unset=True,
                        exclude_none=True,
                        exclude={"access_rights"},
                    )
                )
            )
            # upsert the rights
            if updated_cluster.access_rights:
                for grp, rights in updated_cluster.access_rights.items():
                    insert_stmt = pg_insert(cluster_to_groups).values(
                        **rights.dict(by_alias=True), gid=grp, cluster_id=the_cluster.id
                    )
                    on_update_stmt = insert_stmt.on_conflict_do_update(
                        index_elements=[
                            cluster_to_groups.c.cluster_id,
                            cluster_to_groups.c.gid,
                        ],
                        set_=rights.dict(by_alias=True),
                    )
                    await conn.execute(on_update_stmt)

            clusters_list: List[Cluster] = await self._clusters_from_cluster_ids(
                conn, {cluster_id}
            )
            if not clusters_list:
                raise ClusterNotFoundError(cluster_id)
            the_cluster = clusters_list[0]

            return the_cluster

    async def delete_cluster(
        self,
        primary_group: GroupID,
        standard_groups: List[GroupID],
        all_group: GroupID,
        cluster_id: PositiveInt,
    ) -> None:
        async with self.engine.acquire() as conn:
            clusters_list: List[Cluster] = await self._clusters_from_cluster_ids(
                conn, {cluster_id}
            )
            if not clusters_list:
                raise ClusterNotFoundError(cluster_id)

            the_cluster = clusters_list[0]
            this_user_cluster_access_rights = compute_cluster_access_rights(
                the_cluster, primary_group, standard_groups, all_group
            )
            if not this_user_cluster_access_rights.delete:
                raise ClusterAccessForbidden(cluster_id)

            await conn.execute(sa.delete(clusters).where(clusters.c.id == cluster_id))
