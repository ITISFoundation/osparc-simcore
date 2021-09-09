# dump the database

This command will dump a database to the file ```dump.sql```

```bash
pg_dump --host POSTGRESHOST --username POSTGRES_USER --format c --blobs --verbose --file dump.sql POSTGRESDB
```

# restore the database locally

First a postgres instance must be setup, and the following will allow saving its contents into a docker-volume name POSTGRES_DATA_VOLUME

```bash
export POSTGRES_DATA_VOLUME=aws-production-simcore_postgres_data; docker-compose up
```

This allows connecting to the local postgres instance
```bash
psql -h 127.0.0.1 -p 5432 -U test
```


```sql
CREATE DATABASE simcoredb;
CREATE USER postgres_osparc WITH PASSWORD 'test';
GRANT ALL PRIVILEGES ON DATABASE simcoredb to postgres_osparc;
```

```bash
pg_restore --host 127.0.0.1 --port 5432 --username postgres_osparc -d simcoredb dump.sql
```
