# ``postgres-database`` database migration

Generic single-database configuration.


## Basic workflow

Our database migration is based on [alembic] and emulates [flask-migrate] plugin. The following steps assume that we start from scratch and aim to setup and run migration scripts for a new database.


### Init

```command
alembic init migration
```

Will add a migrations folder to your application. The contents of this folder need to be added to version control along with your other source files.

### Revision

```command
$ alembic revision --autogenerate -m "Adding storage service tables"
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.autogenerate.compare] Detected added table 'file_meta_data'
INFO  [alembic.ddl.postgresql] Detected sequence named 'user_to_projects_id_seq' as owned by integer column 'user_to_projects(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'tokens_token_id_seq' as owned by integer column 'tokens(token_id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'comp_tasks_task_id_seq' as owned by integer column 'comp_tasks(task_id)', assuming SERIAL and omitting
  Generating /home/crespo/devp/osparc-simcore/packages/postgres-database/migration/versions/86f
ca23596da_adding_storage_service_tables.py ... done
```
Auto-generates some scripts under [migration/versions](packages/postgres-database/migration/versions). The migration script **needs to be reviewed and edited**, as Alembic currently does not detect every change you
make to your models. In particular, Alembic is currently unable to detect:
- table name changes,
- column name changes,
- or anonymously named constraints
A detailed summary of limitations can be found in the Alembic autogenerate documentation.
Once finalized, the migration script also needs to be added to version control.

### Upgrade

Then you can apply the migration to the database:
```command
alembic upgrade head
```
Then each time the database models change repeat the migrate and upgrade commands.

To sync the database in another system just refresh the migrations folder from source control and run the upgrade command.


[flask-migrate]:https://flask-migrate.readthedocs.io/en/latest/
[alembic]:https://alembic.sqlalchemy.org/en/latest/


## Migration of databases already online

**Context:**
- There is a database already online and with data that we want to preserve
- There are **no** migration scripts

```command
alembic init migration
# setup config

alembic revision --autogenerate -m "Init tables"
alembic stamp head # stamps the revision database with the given revision but do not run migrations
alembic revision --autogenerate -m "Added column to file_meta_data"
alembic upgrade head
```
