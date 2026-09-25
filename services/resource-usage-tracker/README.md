# resource usage tracker


Service that collects and stores computational resources usage used in osparc-simcore. Also takes care of computation of used osparc credits.


## Credit computation (Collections)
- **PricingPlan**:
  Describe the overall billing plan/package. The pricing plan can be connected to one or more services. A specific pricing plan might be defined also for billing storage costs.
- **PricingUnit**:
  Specifies the various units/tiers within a pricing plan, that denote different options (resources and costs) for running services/storage costs. For example: a specific pricing plan might offer three tiers based on resources: SMALL, MEDIUM, and LARGE.
- **PricingUnitCreditCost**:
  Defines the credit cost for each unit, which can change over time, allowing for pricing flexibility.


## memory profiling with memray

Opt-in [memray](https://bloomberg.github.io/memray/) wrapper around uvicorn in
`docker/boot.sh` (development image only) — see the
[shared runbook](../README.md#memory-profiling-with-memray) for the full how-to.

- variables: `RESOURCE_USAGE_TRACKER_MEMRAY_*` (master switch `RESOURCE_USAGE_TRACKER_MEMRAY_ENABLED`, `live` mode by default, live port `10259`)
- viewer: `docker exec -it "$(docker compose ps -q resource-usage-tracker)" memray live 10259`
