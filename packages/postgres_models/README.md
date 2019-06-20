# simcore postgres models

All models in the database hosted at the ``postgres`` service

## Models

Installs only models
```console

  pip install -r .

```


## Migration

```console
  pip install .[migration]

  # TODO: create an entrypoint around postgres_model that wraps calls to alembic and
  # point to the right `postgres` service.
  #
  alembic init migration
  alembic revision -m "baseline"
  alembic upgrade head

  # Something is similar to https://flask-migrate.readthedocs.io/en/latest/
```
