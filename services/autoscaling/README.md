# autoscaling

Service to auto-scale swarm for both dynamic and computational services


## development

```
make install-dev
make test-dev-unit

# NOTE: there are manual tests that need access to AWS EC2 instances!
```

## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `AUTOSCALING_MEMRAY_*` (master switch `AUTOSCALING_MEMRAY_ENABLED`, live port `10253`)
- viewer: `docker exec -it "$CONTAINER" memray live 10253`
