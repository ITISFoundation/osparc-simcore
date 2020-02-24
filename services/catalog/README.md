# catalog

[![image-size]](https://microbadger.com/images/itisfoundation/catalog. "More on itisfoundation/catalog:staging-latest image")
[![image-badge]](https://microbadger.com/images/itisfoundation/catalog "More on Components Catalog Service image in registry")
[![image-version]](https://microbadger.com/images/itisfoundation/catalog "More on Components Catalog Service image in registry")
[![image-commit]](https://microbadger.com/images/itisfoundation/catalog "More on Components Catalog Service image in registry")

Manages and maintains a catalog of all published components (e.g. macro-algorithms, scripts, etc)

Typical development workflow:

```cmd

$ cd services/catalog
$ make help
Recipes for 'catalog':

devenv               build development environment (using main services/docker-compose-build.yml)
requirements         compiles pip requirements (.in -> .txt)
install-dev install-prod install-ci install app in development/production or CI mode
tests-unit           runs unit tests
tests-integration    runs integration tests against local+production images
run-devel            runs app with pg fixture for development
down                 stops pg fixture
build                builds docker image (using main services/docker-compose-build.yml)
autoformat           runs black python formatter on this service's code [https://black.readthedocs.io/en/stable/]
version-patch        commits version with bug fixes not affecting the cookiecuter config
version-minor        commits version with backwards-compatible API addition or changes (i.e. can replay)
version-major        commits version with backwards-INcompatible addition or changes
replay               re-applies cookiecutter
info                 displays information
clean                cleans all unversioned files in project and temp files create by this makefile
help                 this colorful help


$ make devenv
$ make install-dev
$ make run-devel


$ make tests
$ make build
```




<!-- Add badges urls here-->
[image-size]:https://img.shields.io/microbadger/image-size/itisfoundation/catalog./staging-latest.svg?label=catalog.&style=flat
[image-badge]:https://images.microbadger.com/badges/image/itisfoundation/catalog.svg
[image-version]:https://images.microbadger.com/badges/version/itisfoundation/catalog.svg
[image-commit]:https://images.microbadger.com/badges/commit/itisfoundation/catalog.svg
<!------------------------->
