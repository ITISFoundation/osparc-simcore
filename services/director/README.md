# director


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `DIRECTOR_MEMRAY_*` (master switch `DIRECTOR_MEMRAY_ENABLED`, `live` mode by default, live port `10251`)
- viewer: `docker exec -it "$(docker compose ps -q director)" memray live 10251`
