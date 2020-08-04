# catalog

[![image-size]](https://microbadger.com/images/itisfoundation/catalog. "More on itisfoundation/catalog:staging-latest image")
[![image-badge]](https://microbadger.com/images/itisfoundation/catalog "More on Components Catalog Service image in registry")
[![image-version]](https://microbadger.com/images/itisfoundation/catalog "More on Components Catalog Service image in registry")
[![image-commit]](https://microbadger.com/images/itisfoundation/catalog "More on Components Catalog Service image in registry")

Manages and maintains a catalog of all published components (e.g. macro-algorithms, scripts, etc)

## Development

Typical development workflow:

```cmd
make devenv
source .venv/bin/activate

cd services/api-service
make install-dev
```

Then
```cmd
make run-devel
```
will start the service in development-mode together with a postgres db initialized with test data.  The API can be query using
- http://127.0.0.1:8000/dev/docs: swagger-UI API doc


Finally
```cmd
make tests
make build-devel
make build
```



<!-- Add badges urls here-->
[image-size]:https://img.shields.io/microbadger/image-size/itisfoundation/catalog./staging-latest.svg?label=catalog.&style=flat
[image-badge]:https://images.microbadger.com/badges/image/itisfoundation/catalog.svg
[image-version]:https://images.microbadger.com/badges/version/itisfoundation/catalog.svg
[image-commit]:https://images.microbadger.com/badges/commit/itisfoundation/catalog.svg
<!------------------------->
