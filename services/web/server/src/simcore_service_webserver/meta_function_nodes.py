""" Nodes (services) in a project implemented with python functions (denoted meta-function nodes)


So far, nodes in a project could be front-end, computational or dynamic. The first
was fully implemented in the web-client (e.g. file-picker) while the two last were implemented
independently as black-boxes (i.e. basically only i/o description known) inside of containers. Here
we start a new type of nodes declared as "front-end" but implemented as python functions in the backend.

Meta-function nodes are evaluated in the backend in the pre-run stage of a meta-project run.

An example of meta-function is the "Integers Iterator" node.
"""

from copy import deepcopy
from typing import Callable, Dict, Iterator, Tuple

from models_library.frontend_services_catalog import (
    FRONTEND_SERVICE_KEY_PREFIX,
    iter_service_docker_data,
)
from models_library.projects_nodes import Node, OutputTypes
from models_library.services import ServiceDockerData

_ServiceKeyVersionPair = Tuple[str, str]


# META-FUNCTION IMPLEMENTATIONS ---------------------------------------


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


# META-FUNCTIONS ---------------------------------------------------

# Catalog of front-end (i.e. non-docker) services
FRONTEND_SERVICES_CATALOG: Dict[_ServiceKeyVersionPair, ServiceDockerData] = {
    (s.key, s.version): s for s in iter_service_docker_data()
}


# Maps meta-function nodes with an implementation
FRONTEND_SERVICE_TO_CALLABLE: Dict[_ServiceKeyVersionPair, Callable] = {
    # TODO: ensure inputs/outputs map function signature
    (
        f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range",
        "1.0.0",
    ): linspace_generator,
}


# UTILS ---------------------------------------------------------------


def create_param_node_from_iterator_with_outputs(iterator_node: Node) -> Node:
    """
    Converts an iterator_node with outputs (i.e. evaluated) to a parameter-node
    that represents a constant value.
    """
    #
    # TODO: this MUST be implemented with a more sophisticated mechanism
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
