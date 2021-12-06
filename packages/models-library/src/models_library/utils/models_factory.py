""" Collection of functions to create BaseModel subclasses

"""

from typing import Iterable, Optional, Set, Type

from pydantic import BaseModel, create_model


def _eval_selection(
    all_fiedls: Iterable, include: Optional[Set[str]], exclude: Optional[Set[str]]
):
    # TODO: use dict for deep include/exclude!
    if include is None:
        include = set(all_fiedls)
    if exclude is None:
        exclude = set()

    selection = include - exclude
    return selection


def _extract_fields(
    model_cls: Type[BaseModel],
    *,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None
):
    selection = _eval_selection(model_cls.__fields__.keys(), include, exclude)
    return {
        field.name: (
            field.type_,
            field.default or field.default_factory or (... if field.required else None),
        )
        for field in model_cls.__fields__.values()
        if field.name in selection
    }


# from pydantic.main import inherit_config

# def _extract_config(
#     model_cls: Type[BaseModel],
#     *,
#     include: Optional[Set[str]] = None,
#     exclude: Optional[Set[str]] = None
# ):
#     selection = _eval_selection(model_cls.__fields__.keys(), include, exclude)

#     # TODO: trim all fields based on selection!
#     namespace = {}
#     namespace["fields"] =
#     namespace["schema_extra"] =

#     return inherit_config(model_cls.__config__, model_cls.__config__, **namespace)


def copy_model(
    reference_cls: Type[BaseModel],
    *,
    name: str,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None
) -> Type[BaseModel]:
    """
    Creates a clone of `reference_cls` with a different name and a subset of fields
    """
    fields = _extract_fields(reference_cls, exclude=exclude, include=include)

    _NewModel = create_model(
        __model_name=name,
        __base__=BaseModel,
        __module__=reference_cls.__module__,
        __validators__={
            f: classmethod(v)
            for f, v in reference_cls.__validators__.items()
            if f in fields
        },
        **fields,
    )
    _NewModel.__doc__ = reference_cls.__doc__
    return _NewModel
