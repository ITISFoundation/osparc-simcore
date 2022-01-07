# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from importlib import import_module
from inspect import getmembers, isclass
from pathlib import Path
from typing import List, Optional, Set, Tuple, Type

import models_library
import pytest
from models_library.utils.misc import extract_examples
from pydantic import BaseModel
from pydantic.json import pydantic_encoder

NameClassPair = Tuple[str, Type[BaseModel]]


def get_model_cls(exclude: Optional[Set] = None) -> List[NameClassPair]:
    """Returns a list of all BaseModel derived classes in models_library
    as (class name, class) items
    """

    def is_model_cls(obj) -> bool:
        return isclass(obj) and obj != BaseModel and issubclass(obj, BaseModel)

    exclude = exclude or set()

    model_classes = []
    for filepath in Path(models_library.__file__).resolve().parent.glob("*.py"):
        if not filepath.name.startswith("_"):
            mod = import_module(f"models_library.{filepath.stem}")
            for name, model_cls in getmembers(mod, is_model_cls):
                if name in exclude:
                    continue
                model_classes.append((name, model_cls))

    return model_classes


@pytest.mark.parametrize("class_name, model_cls", get_model_cls())
def test_extract_examples(class_name, model_cls):

    # can extract examples if any
    examples = extract_examples(model_cls)

    # check if correct examples
    for example in examples:
        print(class_name)
        print(json.dumps(example, default=pydantic_encoder, indent=2))
        model_instance = model_cls.parse_obj(example)
        assert isinstance(model_instance, model_cls)
