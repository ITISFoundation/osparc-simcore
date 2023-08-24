# ``postgres-database`` database migration

Generic single-database configuration.

### NOTE: THIS IS DEPRECATED!

This does not need to be run if you want to use alembic with simcore, as the folder-init is already done. Instead navigate your shell to `osparc-simcore/packages/postgres-database/` and follow the instructions at the Makefile there. Only use this Makefile to learn about the tool alembic, dont actually execute the commands listed here!


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


## Use cases
**A table has been altered*

We create a revision script for the change by using the local db as follows:

```bash
pip install -r packages/postgres-database/requirements/dev.txt # install sc-pg package
docker compose -f services/docker-compose.yml -f services/docker-compose-ops.yml up adminer # bring db and ui up
docker ps # find the published port for the db
sc-pg discover -u scu -p adminadmin --port=5432 # discover the db
sc-pg info # what revision are we at?
sc-pg upgrade head # to to latest if necessary
sc-pg review -m "Altered_table_why" # create a revision, note: the string will be part of the script
sc-pg upgrade head # apply the revision
sc-pg downgrade -- -1 # go back to old revision if sth went banana
```
