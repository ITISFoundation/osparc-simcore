import copy
import importlib
import inspect
import itertools
import pkgutil
from collections.abc import Iterator
from contextlib import suppress
from types import ModuleType
from typing import Any, NamedTuple

import pytest
from pydantic import BaseModel


def is_strict_inner(outer_cls: type, inner_cls: type) -> bool:
    #
    # >>> class A:
    # ...    class C:
    # ...      ...
    # >>> class B(A):
    # ...   ...
    # ...
    # >>> A.C
    # <class '__main__.A.C'>
    # >>> B.C
    # <class '__main__.A.C'>
    #
    # C is strict inner from A but not B
    return f"{outer_cls.__name__}.{inner_cls.__name__}" in f"{inner_cls}"


class ModelExample(NamedTuple):
    model_cls: type[BaseModel]
    example_name: str
    example_data: Any


def iter_examples(
    *, model_cls: type[BaseModel], examples: list[Any]
) -> Iterator[ModelExample]:
    for k, data in enumerate(examples):
        yield ModelExample(
            model_cls=model_cls, example_name=f"example_{k}", example_data=data
        )


def walk_model_examples_in_package(package: ModuleType) -> Iterator[ModelExample]:
    """Walks recursively all sub-modules and collects BaseModel.Config examples"""
    assert inspect.ismodule(package)

    yield from itertools.chain(
        *(
            iter_model_examples_in_module(importlib.import_module(submodule.name))
            for submodule in pkgutil.walk_packages(
                package.__path__,
                package.__name__ + ".",
            )
        )
    )


def iter_model_examples_in_module(module: object) -> Iterator[ModelExample]:
    """Iterates on all examples defined as BaseModelClass.model_config["json_schema_extra"]["example"]


    Usage:

        @pytest.mark.parametrize(
            "model_cls, example_name, example_data",
            iter_model_examples_in_module(simcore_service_webserver.storage_schemas),
        )
        def test_model_examples(
            model_cls: type[BaseModel], example_name: int, example_data: Any
        ):
            print(example_name, ":", json.dumps(example_data))
            assert model_cls.model_validate(example_data)
    """

    def _is_model_cls(obj) -> bool:
        with suppress(TypeError):
            # NOTE: issubclass( dict[models_library.services.ConstrainedStrValue, models_library.services.ServiceInput] ) raises TypeError
            is_parametrized = False
            if hasattr(obj, "__parameters__"):
                is_parametrized = len(obj.__parameters__) == 0
            return (
                obj is not BaseModel
                and inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and not is_parametrized
            )
        return False

    assert inspect.ismodule(module)

    for model_name, model_cls in inspect.getmembers(module, _is_model_cls):
        assert model_name  # nosec
        if (
            (model_config := model_cls.model_config)
            and isinstance(model_config, dict)
            and (json_schema_extra := model_config.get("json_schema_extra", {}))
            and isinstance(json_schema_extra, dict)
        ):
            if "example" in json_schema_extra:
                yield ModelExample(
                    model_cls=model_cls,
                    example_name="example",
                    example_data=json_schema_extra["example"],
                )

            elif "examples" in json_schema_extra:
                for index, example in enumerate(json_schema_extra["examples"]):
                    yield ModelExample(
                        model_cls=model_cls,
                        example_name=f"examples_{index}",
                        example_data=example,
                    )


## PYDANTIC MODELS & SCHEMAS -----------------------------------------------------


@pytest.fixture
def model_cls_examples(model_cls: type[BaseModel]) -> dict[str, dict[str, Any]]:
    """
    Extracts examples from pydantic model class Config
    """

    # Use by defining model_cls as test parametrization
    assert model_cls, (
        f"Testing against a {model_cls} model that has NO examples. Add them in Config class. "
        "These are useful to test backwards compatibility and doc. "
        "SEE https://pydantic-docs.helpmanual.io/usage/schema/#schema-customization"
    )

    json_schema_extra: dict = model_cls.model_config.get("json_schema_extra", {})

    # checks exampleS setup in schema_extra
    examples_list = copy.deepcopy(json_schema_extra.get("examples", []))
    assert isinstance(examples_list, list), (
        "OpenAPI and json-schema differ regarding the format for exampleS."
        "The former is a dict and the latter an array. "
        "We follow json-schema here"
        "SEE https://json-schema.org/understanding-json-schema/reference/generic.html"
        "SEE https://swagger.io/docs/specification/adding-examples/"
    )

    # collect all examples and creates fixture -> {example-name: example, ...}
    examples = {
        f"{model_cls.__name__}.example[{index}]": example_
        for index, example_ in enumerate(examples_list)
    }
    if example := copy.deepcopy(json_schema_extra.get("example")):
        examples[f"{model_cls.__name__}.example"] = example

    return examples
