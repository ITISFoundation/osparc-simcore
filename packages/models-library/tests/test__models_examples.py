import json
from itertools import chain
from typing import Any

import models_library
import pytest
from models_library.rest_pagination import Page
from models_library.rpc_pagination import PageRpc
from pydantic import BaseModel
from pytest_simcore.examples.models_library import PAGE_EXAMPLES, RPC_PAGE_EXAMPLES
from pytest_simcore.pydantic_models import (
    ModelExample,
    iter_examples,
    walk_model_examples_in_package,
)

GENERIC_EXAMPLES: list[ModelExample] = [
    *iter_examples(model_cls=Page[str], examples=PAGE_EXAMPLES),
    *iter_examples(model_cls=PageRpc[str], examples=RPC_PAGE_EXAMPLES),
]


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    chain(GENERIC_EXAMPLES, walk_model_examples_in_package(models_library)),
)
def test_all_models_library_models_config_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.model_validate(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"
