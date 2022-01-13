# simcore postgres database

Contains database **models** served by the ``postgres`` service and adds an extension with **migration** tools (e.g. entrypoint that wraps [alembic]'s CLI in a similar way to [flask-migrate]).


## Usage

To install migration tools add ``[migration]`` extra
```bash
  pip install .[migration]

  # If you are using zsh
  pip install '.[migration]' # https://stackoverflow.com/a/30539963/6797695
```
and to call the CLI use
```bash
  simcore-postgres-database --help

  # or a short alias

  sc-pg --help
```
This entrypoing wraps calls to [alembic] commands and customizes it for ``simcore_postgres_database`` models and `postgres` online database.


A typical workflow:

### Discover

```bash
  # Replace with appropriate user and password
  simcore-postgres-database discover -u simcore -p simcore
```

```bash
  simcore-postgres-database info
```

### Review

```bash
  simcore-postgres-database review -m "some message about changes"
```
Auto-generates some scripts under [migration/versions](packages/postgres-database/migration/versions). The migration script **needs to be reviewed and edited**, as Alembic currently does not detect every change you
make to your models. In particular, Alembic is currently unable to detect:
- table name changes,
- column name changes,
- or anonymously named constraints
A detailed summary of limitations can be found in the Alembic autogenerate documentation.
Once finalized, the migration script also needs to be added to version control.

### Upgrade

Upgrades to given revision (get ``info`` to check history)

```bash
  simcore-postgres-database upgrade head
```

[alembic]:https://alembic.sqlalchemy.org/en/latest/
[flask-migrate]:https://flask-migrate.readthedocs.io/en/latest/

## Database Models

## Development

1. In order to create/modify/delete tables one can use sc-pg to start a clean database:

  ```console
  make setup-commit # this will start a clean database and it is visible under http://127.0.0.1:18080/?pgsql=postgres&username=test&db=test&ns=public
  ```

2. Modify the models in [src/simcore_postgres_database/models](src/simcore_postgres_database/models) according to the new needs
3. Create a migration script:

    ```console
    sc-pg review -m "some meaningful message" # this will generate an alembic migration script in [scripts](./scripts)
    sc-pg upgrade # this will apply the generated migration script on the database
    sc-pg downgrade # this will downgrade the database again to the previous state
    ```

    NOTE: when changing the scripts, one needs to delete the current script or the database state will be undefined.
