import copy
import inspect
from typing import Any, Iterator, NamedTuple

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


def iter_model_examples_in_module(module: object) -> Iterator[ModelExample]:
    """Iterates on all examples defined as BaseModelClass.Config.schema_extra["example"]


    Usage:

        @pytest.mark.parametrize(
            "model_cls, example_name, example_data",
            iter_examples(simcore_service_webserver.storage_schemas),
        )
        def test_model_examples(
            model_cls: type[BaseModel], example_name: int, example_data: Any
        ):
            print(example_name, ":", json.dumps(example_data))
            assert model_cls.parse_obj(example_data)
    """
    assert inspect.ismodule(module)

    for model_name, model_cls in inspect.getmembers(
        module, lambda obj: inspect.isclass(obj) and issubclass(obj, BaseModel)
    ):
        assert model_name  # nosec
        if (
            (config_cls := getattr(model_cls, "Config"))
            and inspect.isclass(config_cls)
            and is_strict_inner(model_cls, config_cls)
            and (schema_extra := getattr(config_cls, "schema_extra", {}))
        ):
            if "example" in schema_extra:
                yield ModelExample(
                    model_cls=model_cls,
                    example_name="example",
                    example_data=schema_extra["example"],
                )

            elif "examples" in schema_extra:
                for index, example in enumerate(schema_extra["examples"]):
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

    # checks exampleS setup in schema_extra
    examples_list = copy.deepcopy(model_cls.Config.schema_extra.get("examples", []))
    assert isinstance(examples_list, list), (
        "OpenAPI and json-schema differ regarding the format for exampleS."
        "The former is a dict and the latter an array. "
        "We follow json-schema here"
        "SEE https://json-schema.org/understanding-json-schema/reference/generic.html"
        "SEE https://swagger.io/docs/specification/adding-examples/"
    )

    # check example in schema_extra
    example = copy.deepcopy(model_cls.Config.schema_extra.get("example"))

    # collect all examples and creates fixture -> {example-name: example, ...}
    examples = {
        f"{model_cls.__name__}.example[{index}]": example
        for index, example in enumerate(examples_list)
    }
    if example:
        examples[f"{model_cls.__name__}.example"] = example

    return examples
