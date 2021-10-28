# services

Each folder contains a services that is part of the platform's main stack. There is separate repository https://github.com/ITISFoundation/osparc-ops/ with extra stacks for operations (e.g. monitoring, logging, ...).


## Development Workflow

To build images for development

```!bash
  make build-devel
  make up-devel
```

To build images for production

```!bash
  make build tag-version
  make up-version
```

## Deploying Services

To build and tag these images:

```!bash
  make build tag-version tag-latest
```

To deploy the application in a single-node swarm

```!bash
  make up-latest
```

## Localhost deploy (dev)

- web: http://127.0.0.1:9081/
  - front-end config [/v0/config](http://172.0.0.1:9081/v0/config)
  - health-check [/heath](http://172.0.0.1:9081/health)
  - diagnostics [/v0/diagnostics?top_tracemalloc=10](http://172.0.0.1:9081/v0/diagnostics?top_tracemalloc=10)
  - run-check [/](http://172.0.0.1:9081/)
  - API doc [/dev/doc](http://127.0.0.1:9081/dev/doc)
  - API base entrypoint [/v0](http://127.0.0.1:9081/v0/)

##### Containers
- [portainer](http://127.0.0.1:9000/#/auth): swarm (you set your own pass)
##### Data storage
- [adminer](http://127.0.0.1:18080/?pgsql=postgres&username=simcore&db=simcoredb&ns=): postgres database content viewer
- [redis-commander](http://172.0.0.1:18081): redis content viewer (analogous to adminer for postgres )
- [minio](http://127.0.0.1:9001): s3 storage management viewer
  - ``user=12345678, password=12345678``
##### Network
- [traefik](http://172.0.0.1:8080/dashboard/): reverse proxy dashboard
  - [whoami](http://127.0.0.1:8080/whoami): test service to check traefik

See details in [docker-compose.local.yml](docker-compose.local.yml).

##### Local registry

```!bash
  make local-registry 
```