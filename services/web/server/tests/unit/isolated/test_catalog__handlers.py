from models_library.services import ServiceInput, ServiceOutput
from simcore_service_webserver.catalog__handlers import can_connect


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
