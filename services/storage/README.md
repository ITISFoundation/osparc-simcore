# storage


Service to manage data storage in simcore


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn and the ``celery`` workers (``sto-worker``, ``sto-worker-cpu-bound``) in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `STORAGE_MEMRAY_*` (master switch `STORAGE_MEMRAY_ENABLED`, `live` mode by default, live port `10254`)
- viewer: `docker exec -it "$(docker compose ps -q storage)" memray live 10254`
