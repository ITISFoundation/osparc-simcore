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

# installs all dependencies as well as web/server package in edit-mode
cd services/web/server
pip3 install -r requirements-dev.txt

# runs server.__main__.py e.g.
python3 -m server --help
```

Init database service by hand and fill it with fake data
```bash
# init test db
cd services/web/server/tests/mock
docker-compose up
cd ../../config
python init_db.py
```

Run server
```bash

cd services/web/server
python3 -m server --config config/server-test.yaml

```

---

Build images of ```webserver```

### Debug

```bash
  cd /path/to/simcore/services

  # development image: image gets labeled as services_webserver:dev
  docker-compose -f docker-compose.yml -f docker-compose.debug.yml build webserver
```

### Release

```bash
  cd /path/to/simcore/services

  # production image: image gets labeled as services_webserver:latest
  docker-compose -f docker-compose.yml build webserver
```
