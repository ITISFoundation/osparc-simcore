# dynamic-scheduler

Wil be used as an interface for running and handling the lifecycle of all dynamic services.


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `DYNAMIC_SCHEDULER_MEMRAY_*` (master switch `DYNAMIC_SCHEDULER_MEMRAY_ENABLED`, `live` mode by default, live port `10263`)
- viewer: `docker exec -it "$(docker compose ps -q dynamic-schdlr)" memray live 10263`
