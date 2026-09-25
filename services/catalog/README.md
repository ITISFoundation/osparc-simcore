# catalog

Manages and maintains a catalog of all published components (e.g. macro-algorithms, scripts, etc)


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `CATALOG_MEMRAY_*` (master switch `CATALOG_MEMRAY_ENABLED`, `live` mode by default, live port `10249`)
- viewer: `docker exec -it "$(docker compose ps -q catalog)" memray live 10249`
