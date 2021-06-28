# dask-sidecar

This is a [dask-worker](https://distributed.dask.org/en/latest/worker.html) that works as a sidecar


## Development

Setup environment

```cmd
make devenv
source .venv/bin/activate
cd services/api-service
make install-dev
```


## Dev notes

### 2021.06.10:
  - installed from dynamic-sidecar in current repo, but could have opted for taking sidecar image as a base. The latter would complicate in-host development though, so we start commando here.
  - can be started as scheduler or worker. TODO: scheduler does not need to mount anything
