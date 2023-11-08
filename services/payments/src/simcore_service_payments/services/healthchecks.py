"""

## Types of health checks

Based on the service types, we can categorize health checks based on the actions they take.

- Reboot: When the target is unhealthy, the target should be restarted to recover to a working state.
Container and VM orchestration platforms typically perform reboots.
- Cut traffic: When the target is unhealthy, no traffic should be sent to the target. Service discovery
services and load balancers typically cut traffic from targets in one way or another.

The difference between these is that rebooting attempts to actively repair the target, while cutting
traffic leaves room for the target to repair itself.

In Kubernetes health-checks are called *probes*:
- The health check for reboots is called a *liveness probe*: "Check if the container is alive".
- The health check for cutting traffic is called a *readiness probe*: "Check if the container is ready to receive traffic".

Taken from https://medium.com/polarsquad/how-should-i-answer-a-health-check-aa1fcf6e858e


## docker healthchecks:

    --interval=DURATION (default: 30s)
    --timeout=DURATION (default: 30s)
    --start-period=DURATION (default: 0s)
    --retries=N (default: 3)

    The health check will first run *interval* seconds after the container is started, and
    then again *interval* seconds after each previous check completes.

    If a single run of the check takes longer than *timeout* seconds then the check is considered to have failed (SEE HealthCheckFailed).

    It takes *retries* consecutive failures of the health check for the container to be considered **unhealthy**.

    *start period* provides initialization time for containers that need time to bootstrap. Probe failure during
    that period will not be counted towards the maximum number of retries.

    However, if a health check succeeds during the *start period*, the container is considered started and all consecutive
    failures will be counted towards the maximum number of retries.

Taken from https://docs.docker.com/engine/reference/builder/#healthcheck
"""

# can run some diagnostic tests to determine readiness and livelihood
# e.g. Can we do payments?
#
# - is the gateway ready?
#    - no. log why? alert!
# - is the RUT reachable?
#    - no. log why? alert!
# - is the database reachable?
#    - no. log why? alert!
#

import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from .payments_gateway import PaymentsGatewayApi
from .resource_usage_tracker import ResourceUsageTrackerApi

_logger = logging.getLogger(__name__)


async def check_payments_gateway_liveness(
    payments_gateway_api: PaymentsGatewayApi,
) -> bool:
    alive = await payments_gateway_api.check_liveness()
    _logger.info(
        "liveness check of '%s': %s", payments_gateway_api.client.base_url, alive
    )
    return bool(alive)


async def check_resource_usage_tracker_liveness(rut: ResourceUsageTrackerApi) -> bool:
    alive = await rut.check_liveness()
    _logger.info("liveness check of '%s': %s", rut.client.base_url, alive)
    return bool(alive)


async def check_postgres_liveness(engine: AsyncEngine) -> bool:
    raise NotImplementedError
