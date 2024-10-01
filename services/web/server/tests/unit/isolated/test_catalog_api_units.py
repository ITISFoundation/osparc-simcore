# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
from typing import Any

import pytest
from models_library.function_services_catalog.services import demo_units
from models_library.services import ServiceInput, ServiceOutput
from pint import UnitRegistry
from simcore_service_webserver.catalog._api_units import can_connect


def _create_port_data(schema: dict[str, Any]):
    description = schema.pop("description", schema["title"])

    return {
        "label": schema["title"],
        "description": description,
        "type": "ref_contentSchema",
        "contentSchema": schema,
    }


@pytest.fixture(scope="module")
def unit_registry():
    return UnitRegistry()


@pytest.mark.acceptance_test(
    "Reproduces https://github.com/ITISFoundation/osparc-simcore/issues/4793"
)
def test_can_connect_enums(unit_registry: UnitRegistry):
    enum_port = {
        "displayOrder": 4,
        "label": "Solution method",
        "description": "desc",
        "type": "ref_contentSchema",
        "contentSchema": {
            "title": "Solution method",
            "default": "Iterative (GMRES)",
            "enum": ["Iterative (GMRES)", "FMM-LU"],
        },
    }

    assert can_connect(
        from_output=ServiceOutput.model_validate(enum_port),
        to_input=ServiceInput.model_validate(enum_port),
        units_registry=unit_registry,
    )


@pytest.mark.acceptance_test(
    "Reproduces https://github.com/ITISFoundation/osparc-issues/issues/442"
)
def test_can_connect_generic_data_types(unit_registry: UnitRegistry):
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
        from_output=ServiceOutput.model_validate(file_picker_outfile),
        to_input=ServiceInput.model_validate(input_sleeper_input_1),
        units_registry=unit_registry,
    )

    # data:text/plain  -> data:*/*
    assert can_connect(
        from_output=ServiceOutput.model_validate(input_sleeper_input_1),
        to_input=ServiceInput.model_validate(file_picker_outfile),
        units_registry=unit_registry,
    )


PORTS_WITH_UNITS = [
    {
        "label": "port_W/O_old",
        "description": "output w/o unit old format",
        "type": "integer",
    },
    _create_port_data(
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
    _create_port_data(
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
        from_output=ServiceOutput.model_validate(port_without_unit),
        to_input=ServiceInput.model_validate(port_with_unit),
        units_registry=unit_registry,
    )

    # w -> w/o
    assert can_connect(
        from_output=ServiceOutput.model_validate(port_with_unit),
        to_input=ServiceInput.model_validate(port_without_unit),
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

    from_port = _create_port_data(
        {
            "title": "src",
            "description": "source port",
            "type": "number",
            "x_unit": from_unit,
        }
    )
    to_port = _create_port_data(
        {
            "title": "dst",
            "description": "destination port",
            "type": "number",
            "x_unit": to_unit,
        }
    )

    assert (
        can_connect(
            from_output=ServiceOutput.model_validate(from_port),
            to_input=ServiceInput.model_validate(to_port),
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
