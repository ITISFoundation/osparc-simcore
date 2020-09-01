# director2

[![image-size]](https://microbadger.com/images/itisfoundation/director2. "More on itisfoundation/director2.:staging-latest image")

[![image-badge]](https://microbadger.com/images/itisfoundation/director2 "More on director2 image in registry")
[![image-version]](https://microbadger.com/images/itisfoundation/director2 "More on director2 image in registry")
[![image-commit]](https://microbadger.com/images/itisfoundation/director2 "More on director2 image in registry")

Director service in simcore stack

<!-- Add badges urls here-->
[image-size]:https://img.shields.io/microbadger/image-size/itisfoundation/director2./staging-latest.svg?label=director2.&style=flat
[image-badge]:https://images.microbadger.com/badges/image/itisfoundation/director2.svg
[image-version]https://images.microbadger.com/badges/version/itisfoundation/director2.svg
[image-commit]:https://images.microbadger.com/badges/commit/itisfoundation/director2.svg
<!------------------------->

## Development

Setup environment

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

The latter will start the director2 service in development-mode together with a postgres db initialized with test data. Open the following sites and use the test credentials ``user=key, password=secret`` to manually test the API:

- http://127.0.0.1:8000/docs: redoc documentation
- http://127.0.0.1:8000/dev/docs: swagger type of documentation
