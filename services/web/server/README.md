# web/server

Corresponds to the ```webserver``` service (see all services in ``services/docker-compose.yml``)


## Development

### Manual test on (linux) host

This is how to setup a virtual environment for python, install in *edit mode* the server package
in it and do a test run via the cli
```bash
# create virtual environment
cd path/to/osparc-simcore
python3 -m venv .venv
source .venv/bin/activate

# instals all dependencies as well as web/server package in edit-mode
cd services/web/server
pip3 install -r requirements/dev.txt

# runs server.__main__.py e.g.
simcore-service-webserver --help
```

Run server passing a configuration file (see example under ``services/web/server/src/simcore_service_webserver/config``)
```bash
python3 -m simcore_service_webserver --config path/to/config.yml

# or altenatively, use script entrypoint
simcore-service-webserver -c path/to/config.yml
```

### Disabling $\mu$services

With the configuration file it is possible to start the server and disable the connection to other services. This will obviously limit the functionality of the webserver but
it can be handy mostly to reduce the boot time and complexity while testing or simply to make some
diagnostics. This is an example of how the ``app`` section of the config file might look like:

```yaml
# reduced-config.yml
version: '1.0'
app:
  host: 127.0.0.1
  log_level: DEBUG
  port: 8080
  testing: true
  disable_services:
    - postgres
    - rabbit
# ...
```
and then

```console
usr@machine:~$ simcore-service-webserver -c reduced-config.yml
DEBUG:simcore_service_webserver.settingsconfig:loading config.ignore.yaml
DEBUG:simcore_service_webserver.application:Serving app ...
DEBUG:simcore_service_webserver.application:Initializing app ...
DEBUG:simcore_service_webserver.rest.routing:OAS3 in ~/osparc-simcore/services/web/server/src/simcore_service_webserver/oas3/v1/openapi.yaml
DEBUG:simcore_service_webserver.db.core:Setting up simcore_service_webserver.db.core [service: postgres] ...
WARNING:simcore_service_webserver.db.core:Service 'postgres' explicitly disabled in config
DEBUG:~/osparc-simcore/services/web/server/src/simcore_service_webserver/session.py:Setting up simcore_service_webserver.session ...
DEBUG:~/osparc-simcore/services/web/server/src/simcore_service_webserver/security.py:Setting up simcore_service_webserver.security ...
DEBUG:~/osparc-simcore/services/web/server/src/simcore_service_webserver/computational_backend.py:Setting up simcore_service_webserver.computational_backend [service: rabbit] ...
WARNING:~/osparc-simcore/services/web/server/src/simcore_service_webserver/computational_backend.py:Service 'rabbit' explicitly disabled in config
DEBUG:~/osparc-simcore/services/web/server/src/simcore_service_webserver/statics.py:Setting up simcore_service_webserver.statics ...
DEBUG:~/osparc-simcore/services/web/server/src/simcore_service_webserver/sockets.py:Setting up simcore_service_webserver.sockets ...
DEBUG:simcore_service_webserver.rest.settings:Setting up simcore_service_webserver.rest.settings ...
DEBUG:asyncio:Using selector: EpollSelector
======== Running on http://127.0.0.1:8080 ========
(Press CTRL+C to quit)
```

### RestAPI doc & test

#### Validating and bundling the OAS (OpenAPI specification)
```
make openapi-specs
```
Note that if you are about to modify some JSONSchema specs, you will first have to have the converting tool installed:
```
cd {base_path}/scripts/json-schema-to-openapi-schema
make
```

To access the apidoc page, open http://localhost:8080/apidoc/ and explore http://localhost:8080/apidoc/swagger.yaml?spec=/v1 (i.e. add this in explore entry)
