from typing import Any

from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceOutputGet,
)
from models_library.services import BaseServiceIOModel, ServiceInput, ServiceOutput
from pint import PintError, UnitRegistry

from ._models import get_unit_name, model_factory


def _get_type_name(port: BaseServiceIOModel) -> str:
    _type: str = port.property_type
    if port.property_type == "ref_contentSchema":
        assert port.content_schema is not None  # nosec
        _type = port.content_schema["type"]
    return _type


def _can_convert_units(from_unit: str, to_unit: str, ureg: UnitRegistry) -> bool:
    assert from_unit  # nosec
    assert to_unit  # nosec
    try:
        can: bool = ureg.Quantity(from_unit).check(to_unit)
    except (TypeError, PintError):
        can = False
    return can


def replace_service_input_outputs(
    service: dict[str, Any],
    *,
    unit_registry: UnitRegistry | None = None,
    **export_options,
):
    """Thin wrapper to replace i/o ports in returned service model"""
    # This is a fast solution until proper models are available for the web API

    for input_key in service["inputs"]:
        new_input = model_factory[ServiceInputGet].from_catalog_service_api_model(
            service, input_key, unit_registry
        )
        service["inputs"][input_key] = new_input.dict(**export_options)

    for output_key in service["outputs"]:
        new_output = model_factory[ServiceOutputGet].from_catalog_service_api_model(
            service, output_key, unit_registry
        )
        service["outputs"][output_key] = new_output.dict(**export_options)


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
            from_unit = get_unit_name(from_output)
            to_unit = get_unit_name(to_input)
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
