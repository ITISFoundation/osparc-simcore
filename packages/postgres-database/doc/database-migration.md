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


## Migration of database in production

- Needs downtime?
- Collisions with ongoing requests while migration?
