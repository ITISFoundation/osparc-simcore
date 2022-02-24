""" Nodes (services) in a project implemented with python functions (denoted meta-function nodes)


So far, nodes in a project could be front-end, computational or dynamic. The first
was fully implemented in the web-client (e.g. file-picker) while the two last were implemented
independently as black-boxes (i.e. basically only i/o description known) inside of containers. Here
we start a new type of nodes declared as "front-end" but implemented as python functions in the backend.

Meta-function nodes are evaluated in the backend in the pre-run stage of a meta-project run.

An example of meta-function is the "Integers Iterator" node.
"""

from copy import deepcopy
from typing import Callable, Dict, Iterator, List, Tuple

from models_library.function_services_catalog import (
    FUNCTION_SERVICE_KEY_PREFIX,
    iter_service_docker_data,
)
from models_library.projects_nodes import Node, OutputTypes
from models_library.services import ServiceDockerData, ServiceKey, ServiceVersion
from pydantic import validate_arguments

_ServiceKeyVersionPair = Tuple[str, str]


# META-FUNCTIONS ---------------------------------------------------

# Catalog of front-end (i.e. non-docker) services
FUNCTION_SERVICES_CATALOG: Dict[_ServiceKeyVersionPair, ServiceDockerData] = {
    (s.key, s.version): s for s in iter_service_docker_data()
}


FUNCTION_SERVICE_TO_CALLABLE: Dict[_ServiceKeyVersionPair, Callable] = {}


@validate_arguments
def register(name: ServiceKey, version: ServiceVersion) -> Callable:
    """Maps a service with a callable

    Basically "glues" the implementation to a function node
    """
    key: _ServiceKeyVersionPair = (name, version)

    if key not in FUNCTION_SERVICES_CATALOG.keys():
        raise ValueError(
            f"No definition of {key} found in the {len(FUNCTION_SERVICES_CATALOG)=}"
        )

    if key in FUNCTION_SERVICE_TO_CALLABLE.keys():
        raise ValueError(f"{key} is already registered")

    def _decorator(func: Callable):
        # TODO: ensure inputs/outputs map function signature
        FUNCTION_SERVICE_TO_CALLABLE[key] = func

        # TODO: wrapper(args,kwargs): extract schemas for inputs and use them to validate inputs
        # before running

        return func

    return _decorator


# META-FUNCTION IMPLEMENTATIONS ---------------------------------------


def _linspace_func(
    linspace_start: int = 0, linspace_stop: int = 1, linspace_step: int = 1
) -> Iterator[int]:
    for value in range(linspace_start, linspace_stop, linspace_step):
        yield value


@register(f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/int-range", "1.0.0")
def _linspace_generator(**kwargs) -> Iterator[Dict[str, OutputTypes]]:
    # maps generator with iterable outputs. can have non-iterable outputs
    # as well
    for value in _linspace_func(**kwargs):
        yield {"out_1": value}


def _sensitivity_func(
    paramrefs: List[float],
    paramdiff: List[float],
    diff_or_fact: bool,
) -> Iterator[Tuple[int, List[float], List[float]]]:

    # This code runs in the backend
    assert len(paramrefs) == len(paramdiff)  # nosec

    n_dims = len(paramrefs)

    for i in range(n_dims):
        paramtestplus = deepcopy(paramrefs)
        paramtestminus = deepcopy(paramrefs)

        # inc/dec one dimension at a time
        if diff_or_fact:
            paramtestplus[i] += paramdiff[i]
        else:
            paramtestplus[i] *= paramdiff[i]

        if diff_or_fact:
            paramtestminus[i] -= paramdiff[i]
        else:
            paramtestminus[i] /= paramdiff[i]  # check that not zero

        yield (i, paramtestplus, paramtestminus)


@register(f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/sensitivity", "1.0.0")
def _sensitivity_generator(**kwargs) -> Iterator[Dict[str, OutputTypes]]:

    for i, paramtestplus, paramtestminus in _sensitivity_func(**kwargs):
        yield {"out_1": i, "out_2": paramtestplus, "out_3": paramtestminus}


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

    assert (  # nosec
        iterator_node.key == f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/int-range"
    )  # nosec
    assert iterator_node.version == "1.0.0"  # nosec

    return Node(
        key="simcore/services/frontend/parameter/integer",
        version="1.0.0",
        label=iterator_node.label,
        inputs={},
        inputNodes=[],
        thumbnail="",  # TODO: hack due to issue in projects json-schema
        outputs=deepcopy(iterator_node.outputs),
    )
