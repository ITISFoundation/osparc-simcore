# datcore-adapter

## Development

Setup environment

```cmd
make devenv
source .venv/bin/activate
cd services/api-service
make install-dev
```


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `DATCORE_ADAPTER_MEMRAY_*` (master switch `DATCORE_ADAPTER_MEMRAY_ENABLED`, `live` mode by default, live port `10261`)
- viewer: `docker exec -it "$(docker compose ps -q datcore-adapter)" memray live 10261`
