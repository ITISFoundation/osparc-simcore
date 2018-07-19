# web/server

Corresponds to the ```webserver``` service

## Development


### Manual test on (linux) host

Environment and first run check
```bash
# create virtual environment
cd path/to/osparc-simcore
python3 -m venv .venv
source .venv/bin/activate

# install in dev-mode
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
