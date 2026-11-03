# Migration of a database

Issue 709

## Migration between schema updates

- Database model schemas change with time based on new requirements or fixes
- Deployed databases have already some data that fulfills current schema but not new one
- We need to update these databases to the new schema while keeping its data
- This shall be done with minimal or no downtime of the running databases
- https://sqlalchemy-migrate.readthedocs.io/en/latest/
  - Migration environment templates: ``alembic list_templates``
    - multidb??
  - Multiple alembic environs from [one ini file](https://alembic.sqlalchemy.org/en/latest/cookbook.html#multiple-environments)
  ```
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

- https://stackoverflow.com/questions/42992256/how-do-you-add-migrate-an-existing-database-with-alembic-flask-migrate-if-you-di
```bash
alembic revision --autogenerate -m "Init tables" # to an empty db

# changes to real db con these tables
alembic stamp head

# revision changes
alembic revision --autogenerate -m "Added column to file_meta_data"
alembic upgrade head
```

## Migration between major releases of postgresql

- Major release of PostgreSQL (first two digit groups, e.g. 8.4 and 8.5 are two consecutive major releases) might change the internal storage format

- See https://www.postgresql.org/docs/9.0/migration.html

### Upgrading between major releases: path for developers

The on-disk storage format is NOT forward-compatible: a PostgreSQL 15 server refuses to
start on a data directory created by 14.x. Therefore old data directories must be replaced,
never reused. The schema is managed by Alembic and is unchanged by an engine upgrade, so
`sc-pg upgrade` is a no-op afterwards.

Local volumes created by a 14.x image are incompatible with the new pin
(`postgres:15.19@sha256:...` in `services/docker-compose.yml`, kept identical in the test
compose fixtures and guarded by
`services/web/server/tests/unit/with_dbs/01/test_db.py::test_uses_same_postgres_version`).

To upgrade a local database:

1. If you need to keep the data, dump it with a client >= 15 (the 15 image itself works):
   ```bash
   docker run --rm postgres:15.19@sha256:... \
     pg_dump "postgresql://$POSTGRES_USER@$host:5432/$POSTGRES_DB" -Fc -f /dump/db.dump
   ```
   (For copies imported via `make import-db-from-docker-volume`, re-export from the source
   with a pg_dump >= 15 client.)
2. Stop and remove the old volume — NEVER point the 15.x image at an existing 14.x volume:
   ```bash
   make down-pg   # and down-prod, if used
   docker volume rm $POSTGRES_DATA_VOLUME
   ```
3. Start a fresh 15.x database (`make up-pg` / `make setup-commit`) and, if you dumped it,
   restore:
   ```bash
   docker run --rm postgres:15.19@sha256:... \
     pg_restore -d "postgresql://$POSTGRES_USER@$host:5432/$POSTGRES_DB" /dump/db.dump
   ```
4. Verify: `SHOW server_version;` returns 15.x and `sc-pg info` / `sc-pg upgrade` reach head.

Test fixtures (e.g. `packages/postgres-database/tests/docker-compose.yml`) are stateless and
need no action.


## Migration of database in production

- Needs downtime?
- Collisions with ongoing requests while migration?
