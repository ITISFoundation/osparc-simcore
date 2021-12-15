from copy import deepcopy
from typing import Callable, Dict, Iterator, Tuple

from models_library.frontend_services_catalog import (
    FRONTEND_SERVICE_KEY_PREFIX,
    iter_service_docker_data,
)
from models_library.projects_nodes import Node, OutputTypes
from models_library.services import ServiceDockerData

_ServiceKeyVersionPair = Tuple[str, str]


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
SERVICE_CATALOG: Dict[_ServiceKeyVersionPair, ServiceDockerData] = {
    (s.key, s.version): s for s in iter_service_docker_data()
}


SERVICE_TO_CALLABLES: Dict[_ServiceKeyVersionPair, Callable] = {
    # ensure inputs/outputs map function signature
    (
        f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range",
        "1.0.0",
    ): linspace_generator,
}


def create_param_node_from_iterator_with_outputs(iterator_node: Node):
    #
    # TODO: this should be replaced by a more sophisticated mechanism
    # that can replace any node with equivalent param-node with outputs
    #

    assert iterator_node.key == f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range"
    assert iterator_node.version == "1.0.0"

    return Node(
        key="simcore/services/frontend/parameter/integer",
        version="1.0.0",
        label=iterator_node.label,
        inputs={},
        inputNodes=[],
        thumbnail="",  # FIXME: hack due to issue in projects json-schema
        outputs=deepcopy(iterator_node.outputs),
    )
