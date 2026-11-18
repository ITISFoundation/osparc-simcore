# Postgres configuration

Read and follow instructions in `./scripts/init.sql` script. This needs to be
executed once in every postgres database we run (both self-hosted and RDS).

Create role and users scripts need to be run on demand (e.g. in case we need a
readonly user). Generate scripts using repo config values, read and follow
instructions inside. This needs to be executed once.

## PostgreSQL version

The Postgres image is pinned by tag and digest in `services/docker-compose.yml`.
Keep the same pin in the test Compose fixtures.

For major engine upgrades, follow the
[developer upgrade path](../../packages/postgres-database/doc/database-migration.md#upgrading-between-major-releases-path-for-developers).
PG18 volumes must be mounted at `/var/lib/postgresql`, not the pre-18
`/var/lib/postgresql/data` path. Do not reuse data directories from older major
versions.
