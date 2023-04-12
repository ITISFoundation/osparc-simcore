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

Usage of these tools are demonstrated in packages/models-library/tests/test_utils_pydantic_models_factory.py
"""
import json
import typing
import warnings
from typing import Iterable, Optional

from pydantic import BaseModel, Field, create_model, validator
from pydantic.fields import ModelField, Undefined

warnings.warn(
    "This is still a concept under development. "
    "SEE https://github.com/ITISFoundation/osparc-simcore/issues/2725"
    "Currently only inteded for testing. "
    "DO NOT USE in production.",
    category=UserWarning,
)


def collect_fields_attrs(model_cls: type[BaseModel]) -> dict[str, dict[str, str]]:
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
    include: set[str] | None,
    exclude: set[str] | None,
    exclude_optionals: bool,
) -> set[str]:
    # TODO: use dict for deep include/exclude! SEE https://pydantic-docs.helpmanual.io/usage/exporting_models/

    if include is None:
        include = {f.name for f in model_fields}
    if exclude is None:
        exclude = set()
    if exclude_optionals:
        exclude = exclude.union({f.name for f in model_fields if f.required == False})

    selection = include - exclude
    return selection


def has_optional(t: type):
    origin = typing.get_origin(t)
    args = typing.get_args(t)
    return origin is not None and origin is typing.Union and type(None) in args


def _extract_field_definitions(
    model_cls: type[BaseModel],
    *,
    include: set[str] | None,
    exclude: set[str] | None,
    exclude_optionals: bool,
    set_all_optional: bool,
) -> dict[str, tuple]:
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

    model_field: ModelField

    for model_field in model_cls.__fields__.values():
        if model_field.name in field_names:
            annotation = (
                model_field.type_
                if model_field.type_ == model_field.outer_type_
                else model_field.outer_type_
            )
            if set_all_optional and not has_optional:
                annotation = Optional[annotation]

            field_info = Field(
                default=(
                    model_field.default
                    or model_field.default_factory
                    or (
                        None
                        if set_all_optional or not model_field.required
                        else Undefined
                    )
                ),
                default_factory=model_field.default_factory,
                alias=None
                if model_field.alias == model_field.name
                else model_field.alias,
                title=model_field.field_info.title,
                description=model_field.field_info.description,
                exclude=model_field.field_info.exclude,
                include=model_field.field_info.include,
                const=model_field.field_info.const,
                gt=model_field.field_info.gt,
                ge=model_field.field_info.ge,
                lt=model_field.field_info.lt,
                le=model_field.field_info.le,
                multiple_of=model_field.field_info.multiple_of,
                max_digits=model_field.field_info.max_digits,
                decimal_places=model_field.field_info.decimal_places,
                min_items=model_field.field_info.min_items,
                max_items=model_field.field_info.max_items,
                unique_items=model_field.field_info.unique_items,
                min_length=model_field.field_info.min_length,
                max_length=model_field.field_info.max_length,
                allow_mutation=model_field.field_info.allow_mutation,
                regex=model_field.field_info.regex,
                discriminator=model_field.field_info.discriminator,
                repr=model_field.field_info.repr,
                **model_field.field_info.extra,
            )
            field_definitions[model_field.name] = (annotation, field_info)
    return field_definitions


def copy_model(
    reference_cls: type[BaseModel],
    *,
    name: str = None,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    exclude_optionals: bool = False,
    as_update_model: bool = False,
    skip_validators: bool = False,
    __base__: None | type[BaseModel] | tuple[type[BaseModel], ...] = None,
) -> type[BaseModel]:
    """
    Creates a clone of `reference_cls` with a different name and a subset of fields


    skip_validators: when data source is already validated, there is not need to use these
    validators
    """
    name = name or f"_Base{reference_cls.__name__.upper()}"

    # FIELDS
    fields_definitions = _extract_field_definitions(
        reference_cls,
        exclude=exclude,
        include=include,
        exclude_optionals=exclude_optionals,
        set_all_optional=as_update_model,
    )

    # VALIDATORS

    validators_funs: dict[str, classmethod] = {}
    # A dict of method names and @validator class methods
    # SEE example in https://pydantic-docs.helpmanual.io/usage/models/#dynamic-model-creation
    if not skip_validators and reference_cls != BaseModel:
        for n, vals in reference_cls.__validators__.items():
            for i, v in enumerate(vals):
                validators_funs[f"{n}_validator_{i}"] = validator(n, allow_reuse=True)(
                    v.func
                )

    new_model_cls = create_model(
        name,
        __base__=__base__,
        __module__=reference_cls.__module__,
        __validators__=validators_funs,
        **fields_definitions,
    )

    return new_model_cls
