from models_library.services import ServiceInput, ServiceOutput
from simcore_service_webserver.catalog_handlers_utils import can_connect


def test_can_connect():
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


def test_can_connect_no_units_with_units():
    port_without_unit = {
        "label": "port W/O",
        "description": "output w/o unit",
        "type": "integer",
    }

    port_with_unit = {
        "label": "port W/",
        "description": "port w/ unit",
        "type": "integer",
        "unit": "m",  # <---
    }

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
    assert can_connect(
        from_output=ServiceOutput.parse_obj(port_with_unit),
        to_input=ServiceInput.parse_obj(port_without_unit),
        strict=True,
    )
