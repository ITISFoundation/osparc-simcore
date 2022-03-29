from copy import deepcopy
from typing import Any, Dict, Iterator, List, Tuple

from models_library.projects_nodes import Outputs
from models_library.services import (
    LATEST_INTEGRATION_VERSION,
    ServiceDockerData,
    ServiceType,
)
from pydantic import schema_of

from .._utils import EN, OM, create_fake_thumbnail_url, register_definition
from .._utils_impl import register_implementation
from ..constants import FUNCTION_SERVICE_KEY_PREFIX

LIST_NUMBERS_SCHEMA: Dict[str, Any] = schema_of(List[float], title="list[number]")


META = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/sensitivity",
        "version": "1.0.0",
        "type": ServiceType.BACKEND,
        "name": "Sensitivity iterator",
        "description": "Increases/decreases one dimension of the reference parameters at every iteration",
        "authors": [EN, OM],
        "contact": OM.email,
        "thumbnail": create_fake_thumbnail_url("sensitivity"),
        "inputs": {
            "paramrefs": {
                "label": "paramrefs",
                "description": "reference parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "paramdiff": {
                "label": "paramdiff",
                "description": "diff parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "diff_or_fact": {
                "label": "diff_or_fact",
                "description": "Applies difference (true) or factor (false)",
                "type": "boolean",
            },
        },
        "outputs": {
            "out_1": {
                "label": "i",
                "description": "dimension index that was modified",
                "type": "integer",
            },
            "out_2": {
                "label": "paramtestplus",
                "description": "increased parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "out_3": {
                "label": "paramtestminus",
                "description": "decreased parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
        },
    }
)

REGISTRY = register_definition(META)


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


@register_implementation(
    f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/sensitivity", "1.0.0"
)
def _sensitivity_generator(**kwargs) -> Iterator[Outputs]:

    for i, paramtestplus, paramtestminus in _sensitivity_func(**kwargs):
        yield {"out_1": i, "out_2": paramtestplus, "out_3": paramtestminus}
