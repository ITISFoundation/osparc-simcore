""" Collection of functions to create BaseModel subclasses


Maintaining large models representing a resource can be challenging, specially when every interface (e.g. i/o rest API, i/o db, ...)
needs a slightly different variation of the original domain model. For instance, assume we want to implement an API with CRUD
routes on a resource R. This needs similar models for the request bodies and response payloads to represent R. A careful analysis
reveals that these models are all basically variants that include/exclude fields and/or changes constraints on them (e.g. read-only,
nullable, optional/required, etc).

These variants are typically achived by splitting common fields into smaller models and using inheritance to compose them back
and/or override constraints. Nonetheless, this approach can be very tedious to maintain: it is very verbose and difficult to
see the final model layout. In addition, new variants that exclude fields will force to redesign how all models were split in
the first place.

In order to overcome these drawbacks, we propose here a functional approach based on a model's factory that can "copy the
necessary parts" from a "reference" model and build a new pydantic model that can be either used as new base or as is.

The design should remain as close to pydantic's conventions as possible to reduce maintenance costs
since we are aware that future releases of pydantic will address part of the features we implement here
(e.g. exclude fields)

Usage of these tools are demonstrated in packages/models-library/tests/test_utils_models_factory.py
"""
#
# SEE https://github.com/ITISFoundation/osparc-simcore/issues/2725

import json
from typing import Dict, Iterable, Optional, Set, Tuple, Type

from pydantic import BaseModel, create_model
from pydantic.class_validators import (
    ValidatorGroup,
    extract_validators,
    inherit_validators,
)
from pydantic.fields import ModelField
from pydantic.main import BaseConfig


def collect_fields_attrs(model_cls: Type[BaseModel]) -> Dict[str, Dict[str, str]]:
    """

    >>> class MyModel(BaseModel):
    ...    x : int
    ...
    >>> print(json.dumps(collect_fields_attrs(MyModel), indent=1))
    {
        "x": {
            "type_": "<class 'type'> - int",
            "outer_type_": "<class 'type'> - int",
            "sub_fields": "None",
            "key_field": "None",
            "validators": "[\"<class 'cython_function_or_method'> - int_validator\"]",
            "pre_validators": "None",
            "post_validators": "None",
            "default": "None",
            "default_factory": "None",
            "required": "True",
            "model_config": "<class 'type'> - Config",
            "name": "x",
            "alias": "x",
            "has_alias": "False",
            "field_info": "default=PydanticUndefined extra={}",
            "validate_always": "False",
            "allow_none": "False",
            "shape": "1",
            "class_validators": "{}",
            "parse_json": "False"
        }
    }
    """

    def _stringify(obj):
        if callable(obj):
            obj_str = f"{getattr(obj, '__class__', None)} - {obj.__name__}"
        elif isinstance(obj, dict):
            obj_str = json.dumps(
                {f"{key}": _stringify(value) for key, value in obj.items()}
            )
        elif isinstance(obj, list):
            obj_str = json.dumps([_stringify(item) for item in obj])

        else:
            obj_str = f"{obj}"
            if "object" in obj_str:
                obj_str = obj_str.split("object")[0]

        assert obj_str  # nosec
        return obj_str

    return {
        field.name: {
            attr_name: _stringify(getattr(field, attr_name))
            for attr_name in ModelField.__slots__
        }
        for field in model_cls.__fields__.values()
    }


def _eval_selection(
    model_fields: Iterable[ModelField],
    include: Optional[Set[str]],
    exclude: Optional[Set[str]],
    exclude_optionals: bool,
) -> Set[str]:
    # TODO: use dict for deep include/exclude! SEE https://pydantic-docs.helpmanual.io/usage/exporting_models/

    if include is None:
        include = set(f.name for f in model_fields)
    if exclude is None:
        exclude = set()
    if exclude_optionals:
        exclude = exclude.union(
            set(f.name for f in model_fields if f.required == False)
        )

    selection = include - exclude
    return selection


def _extract_field_definitions(
    model_cls: Type[BaseModel],
    *,
    include: Optional[Set[str]],
    exclude: Optional[Set[str]],
    exclude_optionals: bool,
    set_all_optional: bool,
) -> Dict[str, Tuple]:
    """
    Returns field_definitions: fields of the model in the format
        `<name>=(<type>, <default default>)` or `<name>=<default value>`,
         e.g.
        `foobar=(str, ...)` or `foobar=123`,

        or, for complex use-cases, in the format
        `<name>=<FieldInfo>`,
        e.g.
        `foo=Field(default_factory=datetime.utcnow, alias='bar')`

    """
    field_names = _eval_selection(
        model_cls.__fields__.values(), include, exclude, exclude_optionals
    )
    field_definitions = {}

    field: ModelField

    for field in model_cls.__fields__.values():
        if field.name in field_names:
            field_definitions[field.name] = (
                # <type>
                field.type_ if field.type_ == field.outer_type_ else field.outer_type_,
                # <default value>
                field.default
                or field.default_factory
                or (None if set_all_optional or not field.required else ...),
            )
    return field_definitions


def copy_model(
    reference_cls: Type[BaseModel],
    *,
    name: str = None,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    exclude_optionals: bool = False,
    as_update_model: bool = False,
    skip_validators: bool = False,
    __config__: Type[BaseConfig] = None,
) -> Type[BaseModel]:
    """
    Creates a clone of `reference_cls` with a different name and a subset of fields


    skip_validators: when data source is already validated, there is not need to use these
    validators
    """
    name = name or f"_Base{reference_cls.__name__.upper()}"
    fields_definitions = _extract_field_definitions(
        reference_cls,
        exclude=exclude,
        include=include,
        exclude_optionals=exclude_optionals,
        set_all_optional=as_update_model,
    )

    # A dict of method names and @validator class methods
    validators_funs: Dict[str, classmethod] = {}
    if not skip_validators and reference_cls != BaseModel:
        validators = inherit_validators(extract_validators(reference_cls.__dict__), {})
        vg = ValidatorGroup(validators)
        vg.check_for_unused()
        validators_funs = vg.validators  # pylint: disable=no-member

    new_model_cls = create_model(
        name,
        __config__=__config__,
        __base__=BaseModel,
        __module__=reference_cls.__module__,
        __validators__=validators_funs,
        **fields_definitions,
    )

    return new_model_cls
