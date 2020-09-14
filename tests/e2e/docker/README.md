# Builds the base image for running e2e testing

# Build

```console
make build (or build-kit or build-x depending on installed docker engine)
```

# Testing

```console
make shell
```

# publishing

```console
export DOCKER_IMAGE_TAG=X.X.X
make build
make push
```
