# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from collections.abc import Iterable
from contextlib import suppress
from importlib import import_module
from inspect import getmembers, isclass
from pathlib import Path
from typing import Any

import models_library
import pytest
from models_library.utils.misc import extract_examples
from pydantic import BaseModel, NonNegativeInt
from pydantic.json import pydantic_encoder


def iter_model_cls_examples(
    exclude: set | None = None,
) -> Iterable[tuple[str, type[BaseModel], NonNegativeInt, Any]]:
    def _is_model_cls(cls) -> bool:
        with suppress(TypeError):
            # NOTE: issubclass( dict[models_library.services.ConstrainedStrValue, models_library.services.ServiceInput] ) raises TypeError
            return cls is not BaseModel and isclass(cls) and issubclass(cls, BaseModel)
        return False

    exclude = exclude or set()

    for filepath in Path(models_library.__file__).resolve().parent.glob("*.py"):
        if not filepath.name.startswith("_"):
            mod = import_module(f"models_library.{filepath.stem}")
            for name, model_cls in getmembers(mod, _is_model_cls):
                if name in exclude:
                    continue
                # NOTE: this is part of utils.misc and is tested here
                examples = extract_examples(model_cls)
                for index, example in enumerate(examples):
                    yield (name, model_cls, index, example)


@pytest.mark.parametrize(
    "class_name, model_cls, example_index, test_example", iter_model_cls_examples()
)
def test_all_module_model_examples(
    class_name: str,
    model_cls: type[BaseModel],
    example_index: NonNegativeInt,
    test_example: Any,
):
    """Automatically collects all BaseModel subclasses having examples and tests them against schemas"""
    print(
        f"test {example_index=} for {class_name=}:\n",
        json.dumps(test_example, default=pydantic_encoder, indent=2),
        "---",
    )
    model_instance = model_cls.parse_obj(test_example)
    assert isinstance(model_instance, model_cls)
