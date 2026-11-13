# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from datetime import UTC, datetime, timedelta, timezone
from typing import Final

import pytest
from models_library.api_schemas_catalog.services import ServiceUpdateV2
from models_library.api_schemas_catalog.services_ports import ServicePortGet
from models_library.services import ServiceInput

_CET: Final = timezone(timedelta(hours=2))


def test_service_port_with_file():
    io = ServiceInput.model_validate(
        {
            "displayOrder": 1,
            "label": "Input files",
            "description": "Files downloaded from service connected at the input",
            "type": "data:*/*",  # < --- generic mimetype!
            "fileToKeyMap": {"single_number.txt": "input_1"},  # <-- provides a file with an extension
        }
    )

    port = ServicePortGet.from_domain_model("input", "input_1", io).model_dump(exclude_unset=True)

    assert port == {
        "key": "input_1",
        "kind": "input",
        "content_media_type": "text/plain",  # <-- deduced from extension
        "content_schema": {
            "type": "string",
            "title": "Input files",
            "description": "Files downloaded from service connected at the input",
        },
    }


def test_service_port_with_boolean():
    io = ServiceInput.model_validate(
        {
            "displayOrder": 3,
            "label": "Same title and description is more usual than you might think",
            "description": "Same title and description is more usual than you might think",
            # <- same label and description!
            "type": "boolean",
            "defaultValue": False,  # <- has a default
        }
    )

    port = ServicePortGet.from_domain_model("input", "input_1", io).model_dump(exclude_unset=True)

    assert port == {
        "key": "input_1",
        "kind": "input",
        # "content_media_type": None,  # <-- no content media
        "content_schema": {
            "type": "boolean",
            "title": "Same title and description is more usual than you might think",  # <-- no description
            "default": False,  # <--
        },
    }


@pytest.mark.parametrize(
    "given, expected",
    [
        pytest.param(None, None, id="none"),
        # naive timestamps are the ones stored in the column before it became `timestamptz`
        pytest.param(
            datetime(2099, 1, 19, 12, 45),  # noqa: DTZ001
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            id="naive-interpreted-as-utc",
        ),
        pytest.param(
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            id="utc-unchanged",
        ),
        # an aware value must keep pointing to the same instant
        pytest.param(
            datetime(2099, 1, 19, 14, 45, tzinfo=_CET),
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            id="offset-converted-to-utc",
        ),
    ],
)
def test_service_update_deprecated_is_always_utc(given, expected):
    # `deprecated` lands in a `timestamptz` column, so it must always be bound
    # with an explicit UTC offset
    model = ServiceUpdateV2.model_validate({"deprecated": given})
    assert model.deprecated == expected
    if expected is not None:
        assert model.deprecated is not None
        assert model.deprecated.tzinfo == UTC
