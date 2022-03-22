import itertools
from typing import Any, Dict

import pytest
from models_library.services import ServiceInput, ServiceOutput
from pydantic import Field, create_model
from simcore_service_webserver.catalog_handlers_utils import can_connect

# HELPERS ----------


def create_port_data(schema: Dict[str, Any]):
    description = schema.pop("description", schema["title"])

    return {
        "label": schema["title"],
        "description": description,
        "type": "ref_contentSchema",
        "contentSchema": schema,
    }


def upgrade_port_data(old_port) -> Dict[str, Any]:
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


# TESTS -----------------


def test_can_connect_issue_442():
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
    )
    assert not can_connect(
        from_output=ServiceOutput.parse_obj(file_picker_outfile),
        to_input=ServiceInput.parse_obj(input_sleeper_input_1),
        strict=True,
    )

    # data:text/plain  -> data:*/*
    assert can_connect(
        from_output=ServiceOutput.parse_obj(input_sleeper_input_1),
        to_input=ServiceInput.parse_obj(file_picker_outfile),
    )
    assert can_connect(
        from_output=ServiceOutput.parse_obj(input_sleeper_input_1),
        to_input=ServiceInput.parse_obj(file_picker_outfile),
        strict=True,
    )


ports_with_units = [
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

ports_without_units = [
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
            "x-unit": "cm",  # <---
        }
    ),
]


@pytest.mark.parametrize(
    "port_without_unit, port_with_unit",
    itertools.product(ports_without_units, ports_with_units),
    ids=lambda l: l["label"],
)
def test_can_connect_no_units_with_units(port_without_unit, port_with_unit):
    # w/o -> w
    assert can_connect(
        from_output=ServiceOutput.parse_obj(port_without_unit),
        to_input=ServiceInput.parse_obj(port_with_unit),
    )
    assert not can_connect(
        from_output=ServiceOutput.parse_obj(port_without_unit),
        to_input=ServiceInput.parse_obj(port_with_unit),
        strict=True,
    )

    # w -> w/o
    assert can_connect(
        from_output=ServiceOutput.parse_obj(port_with_unit),
        to_input=ServiceInput.parse_obj(port_without_unit),
    )
    assert not can_connect(
        from_output=ServiceOutput.parse_obj(port_with_unit),
        to_input=ServiceInput.parse_obj(port_without_unit),
        strict=True,
    )
