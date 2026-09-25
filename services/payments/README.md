# payments service

Payment service acts as intermediary between osparc and a `payments-gateway` connected to an external payment system (e.g. stripe, ...). Therefore the
`payments-gateway` acts as a common interface with the final payment system to make osparc independent of that decision. The communication
is implemented using http in two directions. This service communicates with a `payments-gateway` service using an API with this specifications [gateway/openapi.json](gateway/openapi.json)
and the latter is configured to acknowledge back to this service (i.e. web-hook) onto this API with the following specs [openapi.json](openapi.json).

Here is a diagram of how this service interacts with the rest of internal and external services
![[doc/payments.drawio.svg]]

- Further details on the use case and requirements in https://github.com/ITISFoundation/osparc-simcore/issues/4657


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `PAYMENTS_MEMRAY_*` (master switch `PAYMENTS_MEMRAY_ENABLED`, `live` mode by default, live port `10258`)
- viewer: `docker exec -it "$(docker compose ps -q payments)" memray live 10258`
