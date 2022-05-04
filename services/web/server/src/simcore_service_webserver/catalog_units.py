from dataclasses import dataclass
from typing import Optional

from models_library.services import BaseServiceIOModel, ServiceInput, ServiceOutput
from pint import PintError, UnitRegistry

##  MODELS UTILS ---------------------------------


def _get_unit_name(port: BaseServiceIOModel) -> str:
    unit = port.unit
    if port.property_type == "ref_contentSchema":
        assert port.content_schema is not None  # nosec
        unit = port.content_schema.get("x_unit", unit)
        if unit:
            # WARNING: has a special format for prefix. tmp direct replace here
            unit = unit.replace("-", "")
        elif port.content_schema["type"] in ("object", "array"):
            # these objects might have unit in its fields
            raise NotImplementedError
    return unit


def _get_type_name(port: BaseServiceIOModel) -> str:
    _type = port.property_type
    if port.property_type == "ref_contentSchema":
        assert port.content_schema is not None  # nosec
        _type = port.content_schema["type"]
    return _type


@dataclass
class UnitHtmlFormat:
    short: str
    long: str


def get_html_formatted_unit(
    port: BaseServiceIOModel, ureg: UnitRegistry
) -> Optional[UnitHtmlFormat]:
    try:
        unit_name = _get_unit_name(port)
        if unit_name is None:
            return None

        q = ureg.Quantity(unit_name)
        return UnitHtmlFormat(short=f"{q.units:~H}", long=f"{q.units:H}")
    except (PintError, NotImplementedError):
        return None


## PORT COMPATIBILITY ---------------------------------


def _can_convert_units(from_unit: str, to_unit: str, ureg: UnitRegistry) -> bool:
    assert from_unit  # nosec
    assert to_unit  # nosec
    try:
        return ureg.Quantity(from_unit).check(to_unit)
    except (TypeError, PintError):
        return False


def can_connect(
    from_output: ServiceOutput,
    to_input: ServiceInput,
    units_registry: UnitRegistry,
) -> bool:
    """Checks compatibility between ports.

    This check IS PERMISSIVE and is used for checks in the UI where one needs to give some "flexibility" since:
    - has to be a fast evaluation
    - there are no error messages when check fails
    - some configurations might need several UI steps to be valid

    For more strict checks use the "strict" variant
    """
    # types check
    from_type = _get_type_name(from_output)
    to_type = _get_type_name(to_input)

    ok = (
        from_type == to_type
        or (
            # data:  -> data:*/*
            to_type == "data:*/*"
            and from_type.startswith("data:")
        )
        or (
            # NOTE: by default, this is allowed in the UI but not in a more strict plausibility check
            # data:*/*  -> data:
            from_type == "data:*/*"
            and to_type.startswith("data:")
        )
    )

    if any(t in ("object", "array") for t in (from_type, to_type)):
        # Not Implemented but this if e.g. from_type == to_type that should be the answer
        return ok

    # types units
    if ok:
        try:
            from_unit = _get_unit_name(from_output)
            to_unit = _get_unit_name(to_input)
        except NotImplementedError:
            return ok

        ok = ok and (
            from_unit == to_unit
            # unitless -> *
            or from_unit is None
            # * -> unitless
            or to_unit is None
            # from_unit -> unit
            or _can_convert_units(from_unit, to_unit, units_registry)
        )

    return ok
