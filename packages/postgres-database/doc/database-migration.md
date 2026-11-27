# Migration of a database

Issue 709

## Migration between schema updates

- Database model schemas change with time based on new requirements or fixes
- Deployed databases have already some data that fulfills current schema but not
  new one
- We need to update these databases to the new schema while keeping its data
- This shall be done with minimal or no downtime of the running databases
- <https://sqlalchemy-migrate.readthedocs.io/en/latest/>
  - Migration environment templates: ``alembic list_templates``
    - multidb??
  - Multiple alembic environs from [one ini file](https://alembic.sqlalchemy.org/en/latest/cookbook.html#multiple-environments)

```bash
alembic init migration
alembic revision -m "baseline"
alembic upgrade head
alembic revision -m "first tables"
alembic upgrade head
alembic revision -m "add column"

alembic info
alembic list_templates
alembic current
alembic downgrade -1
alembic head
alembic upgrade head
alembic history
```

- what autogenerate [does NOT decect](https://alembic.sqlalchemy.org/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect)

- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)

```bash
alembic revision --autogenerate -m "Init tables" # to an empty db

# changes to real db con these tables
alembic stamp head

# revision changes
alembic revision --autogenerate -m "Added column to file_meta_data"
alembic upgrade head
```

### Upgrading between major releases: path for developers

The on-disk storage format is NOT forward-compatible: a PostgreSQL 18 server
refuses to start on a data directory created by 14.x. Therefore old data
directories must be replaced, never reused. The schema is managed by Alembic and
is unchanged by an engine upgrade, so `sc-pg upgrade` is a no-op if the database
is already at the current schema revision.

Local volumes created by a 14.x image are incompatible with the new pin
(`postgres:18.6@sha256:...` in `services/docker-compose.yml`), kept identical in
the test Compose fixtures and guarded by
`packages/pytest-simcore/tests/test_postgres_tools_templates.py::test_uses_same_postgres_image`.

To upgrade a local database:

1. If you need to keep the data, dump it with a client >= 18:

   ```bash
   PG_IMAGE=$(docker compose -f tests/docker-compose.yml config --format json |
     jq -r '.services.postgres.image')
   docker run --rm --network host -v "$PWD:/dump" -e PGPASSWORD "$PG_IMAGE" \
     pg_dump "postgresql://$POSTGRES_USER@$host:5432/$POSTGRES_DB" \
     -Fc -f /dump/db.dump
   ```

   For copies imported via `make import-db-from-docker-volume`, re-export from
   the source with a pg_dump >= 18 client.

1. Stop and remove the old volume. Never point the 18.x image at an existing
   14.x volume:

   ```bash
   make down-pg   # and down-prod, if used
   docker volume rm "$POSTGRES_DATA_VOLUME"
   ```

1. Start a fresh 18.x database (`make up-pg` / `make setup-commit`) and restore
   the dump if you created one:

   ```bash
   docker run --rm --network host -v "$PWD:/dump:ro" -e PGPASSWORD "$PG_IMAGE" \
     pg_restore -d "postgresql://$POSTGRES_USER@$host:5432/$POSTGRES_DB" \
     --exit-on-error /dump/db.dump
   ```

1. Verify that `SHOW server_version;` returns 18.x and that `sc-pg info` /
   `sc-pg upgrade` reach head.

Test fixtures (e.g. `packages/postgres-database/tests/docker-compose.yml`) are
stateless and need no action.

## Migration of database in production

- Needs downtime?
- Collisions with ongoing requests while migration?
