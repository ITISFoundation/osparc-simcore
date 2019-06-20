# simcore postgres models

All models in the database hosted at the ``postgres`` service


## Migration

```console
  pip install simcore-postgres-models[migration]


  # TODO: create an entrypoint around postgres_model that wraps calls to alembic and
  # point to the right `postgres` service.
  #
  alembic init migration
  alembic revision -m "baseline"
  alembic upgrade head

  # Something is similar to https://flask-migrate.readthedocs.io/en/latest/
```
