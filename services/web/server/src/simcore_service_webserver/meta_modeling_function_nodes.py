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

from models_library.frontend_services_catalog import (
    FRONTEND_SERVICE_KEY_PREFIX,
    OM,
    ServiceType,
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


def _linspace_generator(**kwargs) -> Iterator[Dict[str, OutputTypes]]:
    # maps generator with iterable outputs. can have non-iterable outputs
    # as well
    for value in _linspace_func(**kwargs):
        yield {"out_1": value}


# TODO: extend InputTypes/OutputTypes to List[T]
# TODO: pydantic map to json-schema

# TODO: inputs need to match _func definition!
# TODO: _sensitivity_meta needs to go in frontend_service_cantalog and registered in there so that
# the catalog can identify this service

# TODO: inject in database (including code??) If so, the definition can even change??


def _sensitivity_meta() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/sensitivity",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Sensitivity iterator",
        description="Increases/decreases one dimension of the reference parameters at every iteration",
        authors=[
            OM,
        ],
        contact=OM.email,
        **_sensitivity_schema(),
    )


def _sensitivity_schema():
    return {
        "inputs": {
            "in_1": {
                "label": "paramrefs",
                "description": "reference parameters",
                "type": List[
                    float
                ],  # TODO: check how pydantic maps with python with jsonschema
            },
            "in_2": {
                "label": "paramdiff",
                "description": "diff parameters",
                "type": List[float],
            },
            "in_3": {
                "label": "diff_or_fact",
                "description": "Applies difference (true) or factor (false)",
                "type": bool,
            },
        },
        "outputs": {
            "out_1": {
                "label": "i",
                "description": "dimension index that was modified",
                "type": int,
            },
            "out_2": {
                "label": "paramtestplus",
                "description": "increased parameter",
                "type": List[float],
            },
            "out_3": {
                "label": "paramtestminus",
                "description": "decreased parameter",
                "type": List[float],
            },
        },
    }


def _sensitivity_func(
    paramrefs: List[float],
    paramdiff: List[float],
    diff_or_fact: bool,
):
    # This code runs in the backend
    assert len(paramrefs) == len(paramdiff)

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


def _sensitivity_generator(**kwargs) -> Iterator[Dict[str, OutputTypes]]:
    for i, paramtestplus, paramtestminus in _sensitivity_func(**kwargs):
        yield {"out_1": i, "out_2": paramtestplus, "out_3": paramtestminus}


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
    ): _linspace_generator,
    (
        f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/sensitivity",
        "1.0.0",
    ): _sensitivity_generator,
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

    assert (
        iterator_node.key == f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range"
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
