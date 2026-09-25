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


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around gunicorn (``--follow-fork`` captures master and workers) in
`docker/boot.sh` (development image only) — see the
[shared runbook](../../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `WEBSERVER_MEMRAY_*` (master switch `WEBSERVER_MEMRAY_ENABLED`, defaults to `file` mode, live port `10248`)
- clone switches: `WB_GC_MEMRAY_ENABLED`, `WB_AUTH_MEMRAY_ENABLED`, `WB_DB_EL_MEMRAY_ENABLED` (ports 10265-10267)
- live mode: set `WEBSERVER_MEMRAY_MODE=live` (captures the gunicorn master only), then
 `docker exec -it "$(docker compose ps -q webserver)" memray live 10248`
- file mode: render the captures in `web/server/.ignore/memray/` (master + workers included) with
 `docker exec <container> memray flamegraph -f /tmp/memray/<file>` and open the HTML
