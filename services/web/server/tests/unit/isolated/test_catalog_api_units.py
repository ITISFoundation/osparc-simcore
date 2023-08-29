# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
from typing import Any

import pytest
from models_library.function_services_catalog.services import demo_units
from models_library.services import ServiceInput, ServiceOutput
from pint import UnitRegistry
from pydantic import Field, create_model
from simcore_service_webserver.catalog._api_units import can_connect


def create_port_data(schema: dict[str, Any]):
    description = schema.pop("description", schema["title"])

    return {
        "label": schema["title"],
        "description": description,
        "type": "ref_contentSchema",
        "contentSchema": schema,
    }


def upgrade_port_data(old_port) -> dict[str, Any]:
    _type = old_port["type"]
    if _type in ("number", "integer", "string"):
        # creates schema from old data
        title = old_port["label"].upper()
        field_kwargs = {"description": old_port["description"]}
        if unit := old_port.get("unit"):
            field_kwargs["x_unit"] = unit
        python_type = {"number": float, "integer": int, "string": str}
        schema = create_model(
            title, __root__=(python_type[_type], Field(..., **field_kwargs))
        ).schema_json(indent=1)
        return create_port_data(schema)
    return old_port


@pytest.fixture(scope="module")
def unit_registry():
    return UnitRegistry()


def test_can_connect_for_gh_osparc_issues_442(unit_registry: UnitRegistry):
    # Reproduces https://github.com/ITISFoundation/osparc-issues/issues/442
    file_picker_outfile = {
        "displayOrder": 2,
        "label": "File Picker",
        "description": "Picker",
        "type": "data:*/*",
    }

    input_sleeper_input_1 = {
        "displayOrder": 1,
        "label": "Sleeper",
        "description": "sleeper input file",
        "type": "data:text/plain",
    }

    # data:*/* -> data:text/plain
    assert can_connect(
        from_output=ServiceOutput.parse_obj(file_picker_outfile),
        to_input=ServiceInput.parse_obj(input_sleeper_input_1),
        units_registry=unit_registry,
    )

    # data:text/plain  -> data:*/*
    assert can_connect(
        from_output=ServiceOutput.parse_obj(input_sleeper_input_1),
        to_input=ServiceInput.parse_obj(file_picker_outfile),
        units_registry=unit_registry,
    )


PORTS_WITH_UNITS = [
    {
        "label": "port_W/O_old",
        "description": "output w/o unit old format",
        "type": "integer",
    },
    create_port_data(
        {
            "title": "port-W/O",
            "description": "output w/o unit",
            "type": "integer",
        }
    ),
]

PORTS_WITHOUT_UNITS = [
    {
        "label": "port_W/_old",
        "description": "port w/ unit old format",
        "type": "integer",
        "unit": "m",  # <---
    },
    create_port_data(
        {
            "title": "port-W/",
            "description": "port w/ unit",
            "type": "integer",
            "x_unit": "cm",  # <---
        }
    ),
]


@pytest.mark.parametrize(
    "port_without_unit, port_with_unit",
    itertools.product(PORTS_WITHOUT_UNITS, PORTS_WITH_UNITS),
    ids=lambda l: l["label"],
)
def test_can_connect_no_units_with_units(
    port_without_unit, port_with_unit, unit_registry: UnitRegistry
):
    # w/o -> w
    assert can_connect(
        from_output=ServiceOutput.parse_obj(port_without_unit),
        to_input=ServiceInput.parse_obj(port_with_unit),
        units_registry=unit_registry,
    )

    # w -> w/o
    assert can_connect(
        from_output=ServiceOutput.parse_obj(port_with_unit),
        to_input=ServiceInput.parse_obj(port_without_unit),
        units_registry=unit_registry,
    )


@pytest.mark.parametrize(
    "from_unit, to_unit, are_compatible",
    [
        ("cm", "mm", True),
        ("m", "cm", True),
        ("cm", "miles", True),
        ("foot", "cm", True),
        ("cm", "degrees", False),
        ("cm", None, True),
        (None, "cm", True),
    ],
)
def test_units_compatible(
    from_unit, to_unit, are_compatible, unit_registry: UnitRegistry
):
    #
    # TODO: does it make sense to have a string or bool with x_unit??
    #

    from_port = create_port_data(
        {
            "title": "src",
            "description": "source port",
            "type": "number",
            "x_unit": from_unit,
        }
    )
    to_port = create_port_data(
        {
            "title": "dst",
            "description": "destination port",
            "type": "number",
            "x_unit": to_unit,
        }
    )

    assert (
        can_connect(
            from_output=ServiceOutput.parse_obj(from_port),
            to_input=ServiceInput.parse_obj(to_port),
            units_registry=unit_registry,
        )
        == are_compatible
    )


@pytest.mark.parametrize(
    "from_port,to_port",
    itertools.product(
        demo_units.META.outputs.values(), demo_units.META.inputs.values()
    ),
    ids=lambda p: p.label,
)
def test_can_connect_with_units(
    from_port: ServiceOutput, to_port: ServiceInput, unit_registry: UnitRegistry
):
    # WARNING: assumes the following convention for the fixture data:
    #   - two ports are compatible if they have the same title
    #
    # NOTE: this assumption will probably break when the demo_units service
    # is modified. At that point, please create a fixture in this test-suite
    # and copy&paste inputs/outputs above
    are_compatible = (
        from_port.content_schema["title"] == to_port.content_schema["title"]
    )

    assert (
        can_connect(
            from_output=from_port,
            to_input=to_port,
            units_registry=unit_registry,
        )
        == are_compatible
    )
