""" Service healthcheck


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


import asyncio
import inspect
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

from aiohttp import web
from aiosignal import Signal

from ._constants import APP_SETTINGS_KEY

_HealthCheckSlot = Callable[[web.Application], Awaitable[None]]

if TYPE_CHECKING:
    _HealthCheckSignal = Signal[_HealthCheckSlot]

else:
    _HealthCheckSignal = Signal


class HealthCheckFailed(RuntimeError):
    """Failed a health check

    NOTE: not the same as unhealthy. Check module's doc
    """


class HealthCheck:
    def __init__(self, app: web.Application):
        self._on_healthcheck = Signal(owner=self)  # type: _HealthCheckSignal

        # The docker engine healthcheck: If a single run of the check takes longer than *timeout* seconds
        # then the check is considered to have failed. Therefore there is no need to continue run
        self._timeout: Optional[int] = app[APP_SETTINGS_KEY].SC_HEALTHCHECK_TIMEOUT

    def __repr__(self):
        return "<HealthCheck timeout={}, #on_healthcheck-slots={}>".format(
            self._timeout, len(self._on_healthcheck)
        )

    @property
    def on_healthcheck(self) -> _HealthCheckSignal:
        """Signal to define a health check.
        WARNING: can append **async** slot function. SEE _HealthCheckSlot
        """
        return self._on_healthcheck

    @staticmethod
    def get_app_info(app: web.Application):
        """Minimal (header) health report is information about the app"""
        settings = app[APP_SETTINGS_KEY]
        return {
            "name": settings.APP_NAME,
            "version": settings.API_VERSION,
            "api_version": settings.API_VERSION,
        }

    async def run(self, app: web.Application) -> Dict[str, Any]:
        """Runs all registered checks to determine the service health.

        can raise HealthCheckFailed
        """
        # Ensures no more signals append after first run
        self._on_healthcheck.freeze()

        assert all(  # nosec
            inspect.iscoroutinefunction(fun) for fun in self._on_healthcheck
        ), "All Slot functions that append to on_healthcheck must be coroutines. SEE _HealthCheckSlot"

        try:
            heath_report: Dict[str, Any] = self.get_app_info(app)

            # TODO: every signal could return some info on the health on each part
            # that is appended on heath_report
            await asyncio.wait_for(
                self._on_healthcheck.send(app), timeout=self._timeout
            )

            return heath_report

        except asyncio.TimeoutError as err:
            raise HealthCheckFailed("Service is slowing down") from err
