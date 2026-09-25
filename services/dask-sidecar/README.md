# dask-sidecar

This is a [dask-worker](https://distributed.dask.org/en/latest/worker.html) that works as a sidecar


## Development

Setup environment

```cmd
make devenv
source .venv/bin/activate
cd services/api-service
make install-dev
```


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around the ``dask scheduler``/``dask worker`` entrypoints in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `DASK_SIDECAR_MEMRAY_*` (master switch `DASK_SIDECAR_MEMRAY_ENABLED`, defaults to `file` mode, live port `10262`)
- live mode: set `DASK_SIDECAR_MEMRAY_MODE=live` (captures the master process only), then
 `docker exec -it "$(docker compose ps -q dask-sidecar)" memray live 10262`
- file mode: render the captures in `.ignore/memray/` (master + workers included) with
 `docker exec <container> memray flamegraph -f /tmp/memray/<file>` and open the HTML
