from ._identity import IdentityJsonStr


async def _get_active_user_with(
    self, identity: IdentityJsonStr
) -> _UserIdentity | None:
    # NOTE: Keeps a cache for a few seconds. Observed successive streams of this query
    user: _UserIdentity | None = self.timed_cache.get(identity, None)
    if user is None:
        async with self.engine.acquire() as conn:
            # NOTE: sometimes it raises psycopg2.DatabaseError in #880 and #1160
            result: ResultProxy = await conn.execute(
                sa.select(users.c.id, users.c.role).where(
                    (users.c.email == identity) & (users.c.status == UserStatus.ACTIVE)
                )
            )
            row = await result.fetchone()
        if row is not None:
            assert row["id"]  # nosec
            assert row["role"]  # nosec
            self.timed_cache[identity] = user = _UserIdentity(id=row.id, role=row.role)

    return user
