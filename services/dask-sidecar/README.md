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

## Deploy on a specific cluster

1. define label on docker engine

  ```bash
  sudo nano /etc/docker/daemon.json
  ```

  ```json
  {
    "labels":["cluster_id=MYCLUSTERUNIQUEIDENTIFIER"]
  }
  ```

2. restart the docker engine

  ```bash
  sudo service docker restart
  ```

3. verify

  ```bash
  docker info --format "{{.Labels}}"
  ```


## Dev notes

### 2021.08.24

  - sidecar sets up its own available resources on start
  - sidecar checks local docker engine labels to get its cluster_id

### 2021.06.10

  - installed from dynamic-sidecar in current repo, but could have opted for taking sidecar image as a base. The latter would complicate in-host development though, so we start commando here.
  - can be started as scheduler or worker. TODO: scheduler does not need to mount anything
