from typing import Callable, Dict, Iterator, Tuple

from models_library.frontend_services_catalog import (
    FRONTEND_SERVICE_KEY_PREFIX,
    iter_service_docker_data,
)
from models_library.projects_nodes import OutputTypes


def _linspace_func(
    linspace_start: int = 0, linspace_stop: int = 1, linspace_step: int = 1
) -> Iterator[int]:
    for value in range(linspace_start, linspace_stop, linspace_step):
        yield value


def linspace_generator(**kwargs) -> Iterator[Dict[str, OutputTypes]]:
    # maps generator with iterable outputs. can have non-iterable outputs
    # as well
    for value in _linspace_func(**kwargs):
        yield {"out_1": value}


# For non-docker services
SERVICE_CATALOG = {(s.key, s.version): s for s in iter_service_docker_data()}


SERVICE_TO_CALLABLES: Dict[Tuple[str, str], Callable] = {
    # ensure inputs/outputs map function signature
    (
        f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range",
        "1.0.0",
    ): linspace_generator,
}
