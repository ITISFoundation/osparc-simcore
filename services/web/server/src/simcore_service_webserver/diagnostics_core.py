import logging

from typing import Any, Dict, Optional

from aiohttp import web

from servicelib.incidents import LimitedOrderedStack, SlowCallback


log = logging.getLogger(__name__)

# APP KEYS ---

APP_KEY = f"{__name__}.{{0}}"  # use as APP_KEY.format("variable name")

K_HEALTHCHECK_RETRY = f"{__name__}.health_check_retry"
K_REGISTRY = f"{__name__}.registry"
K_MAX_DELAY_ALLOWED = f"{__name__}.max_delay_allowed"
K_MAX_CANCEL_RATE = f"{__name__}.max_cancelations_rate"
K_MAX_AVG_RESP_DELAY = f"{__name__}.max_avg_response_delay_secs"


def get_param(app: web.Application, name: str) -> Any:
    return app[f"{__name__}.{name}"]


def get_params(app: web.Application) -> Dict[str, Any]:
    params = {key: app[key] for key in app.keys() if key.startswith(f"{__name__}.")}
    return params


# ERRORS ----

class DiagnosticError(Exception):
    pass

class UnhealthyAppError(DiagnosticError):
    pass



class IncidentsRegistry(LimitedOrderedStack[SlowCallback]):
    def max_delay(self) -> float:
        return self.max_item.delay_secs if self else 0


def assert_healthy_app(app: web.Application) -> None:
    """ Diagnostics function that determins whether
        current application is healthy based on incidents
        occured up to now

        raises DiagnosticError if any incient detected
    """
    incidents: Optional[IncidentsRegistry] = app.get(K_REGISTRY)
    if incidents:
        max_delay_allowed: float = app[K_MAX_DELAY_ALLOWED]
        max_delay: float = incidents.max_delay()

        # criteria 1:
        if max_delay > max_delay_allowed:
            msg = "{:3.1f} secs delay [at most {:3.1f} secs allowed]".format(
                max_delay, max_delay_allowed,
            )
            raise UnhealthyAppError(msg)

        # TODO: add more criteria
