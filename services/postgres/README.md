## Postgres configuration

Read and follow instructions in `./scripts/init.sql` script. This needs to be executed once in every postgres database we run (both self-hosted and RDS)

Create role and users scripts need to be run on demand (e.g. in case we need a readonly user). Generate scripts using repo config values, read and follow instructions inside. This needs to be executed once.

## PostgreSQL version

The postgres image is pinned (tag + digest) in `services/docker-compose.yml`. The same pin
must be kept in sync with the test compose fixtures.

For major engine upgrades (e.g. 14.x -> 15.x), follow the developer upgrade path in
[packages/postgres-database/doc/database-migration.md](../../packages/postgres-database/doc/database-migration.md#upgrading-between-major-releases-path-for-developers).
