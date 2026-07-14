# web/server

Corresponds to the ```webserver``` service (see all services in ``services/docker-compose.yml``)

It exposes the REST/WebSocket API consumed by the frontend and hosts most of the platform's
domain logic (e.g. auth, users, projects, products). Some domains are extended by dedicated
satellite services (e.g. `invitations`, `catalog`) so they can scale independently.

See [docs/DESIGN.md](docs/DESIGN.md) for the architecture and design guidelines, and
[docs/TESTS.md](docs/TESTS.md) for the testing conventions used in this service.

## Development

### Setup

Uses the repo-base virtual environment (see repo root `Makefile`, target `devenv`):
```bash
cd path/to/osparc-simcore
make devenv
source .venv/bin/activate

# installs web/server + dev dependencies in edit-mode
cd services/web/server
make install-dev
```
