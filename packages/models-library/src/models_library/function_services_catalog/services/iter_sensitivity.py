from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from pydantic import TypeAdapter

from ...projects_nodes import OutputID, OutputsDict
from ...services import ServiceMetaDataPublished, ServiceType
from ...services_constants import LATEST_INTEGRATION_VERSION
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import EN, OM, FunctionServices, create_fake_thumbnail_url

LIST_NUMBERS_SCHEMA: dict[str, Any] = {
    **TypeAdapter(list[float]).json_schema(),
    "title": "list[number]",
}


META = ServiceMetaDataPublished.model_validate(
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


def eval_sensitivity(
    *,
    paramrefs: list[float],
    paramdiff: list[float],
    diff_or_fact: bool,
) -> Iterator[tuple[int, list[float], list[float]]]:
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


def _sensitivity_generator(
    paramrefs: list[float], paramdiff: list[float], diff_or_fact: bool
) -> Iterator[OutputsDict]:
    for i, paramtestplus, paramtestminus in eval_sensitivity(
        paramrefs=paramrefs, paramdiff=paramdiff, diff_or_fact=diff_or_fact
    ):
        yield {
            OutputID("out_1"): i,
            OutputID("out_2"): paramtestplus,
            OutputID("out_3"): paramtestminus,
        }


services = FunctionServices()
services.add(
    meta=META,
    implementation=_sensitivity_generator,
    is_under_development=True,
)
