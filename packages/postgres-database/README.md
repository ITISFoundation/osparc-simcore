# simcore postgres database

Contains database **models** served by the ``postgres`` service and adds an extension with **migration** tools (e.g. entrypoint that wraps [alembic]'s CLI in a similar way to [flask-migrate]).


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
