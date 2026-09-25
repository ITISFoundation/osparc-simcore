# agent


To develop this project, just

```cmd
make help

```


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `AGENT_MEMRAY_*` (master switch `AGENT_MEMRAY_ENABLED`, `live` mode by default, live port `10260`)
- viewer: `docker exec -it "$(docker compose ps -q agent)" memray live 10260`
