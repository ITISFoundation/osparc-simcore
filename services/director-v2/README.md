# director-v2

Director service in simcore stack

## Development

Since services are often heavily interconnected, it's best to build and run the entire osparc repo in the development mode.
Instruction can be found in the [development build](../../README.md#development-build) section of the main README.


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `DIRECTOR_V2_MEMRAY_*` (master switch `DIRECTOR_V2_MEMRAY_ENABLED`, `live` mode by default, live port `10250`)
- viewer: `docker exec -it "$(docker compose ps -q director-v2)" memray live 10250`
