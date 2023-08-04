import datetime
from uuid import uuid4

import pytest
from models_library.api_schemas_storage import FileMetaDataGet
from pydantic import parse_obj_as
from simcore_service_webserver.projects._nodes_api import _get_files_with_thumbnails

_PROJECT_ID = uuid4()
_NODE_ID = uuid4()
_UTC_NOW = datetime.datetime.now(tz=datetime.timezone.utc)


def _c(file_name: str) -> FileMetaDataGet:
    """simple converter utility"""
    return parse_obj_as(
        FileMetaDataGet,
        {
            "file_uuid": f"{_PROJECT_ID}/{_NODE_ID}/{file_name}",
            "location_id": 0,
            "file_name": file_name,
            "file_id": f"{_PROJECT_ID}/{_NODE_ID}/{file_name}",
            "created_at": _UTC_NOW,
            "last_modified": _UTC_NOW,
        },
    )


def _get_comparable(
    entries: list[tuple[FileMetaDataGet, FileMetaDataGet]]
) -> set[tuple[str, str]]:
    return {(x[0].file_id, x[1].file_id) for x in entries}


@pytest.mark.parametrize(
    "assets_files, expected_result",
    [
        pytest.param(
            [_c("f.bin"), _c("f.bin.png")],
            [(_c("f.bin"), _c("f.bin.png"))],
            id="test_extension_png",
        ),
        pytest.param(
            [_c("f.bin"), _c("f.bin.jpg")],
            [(_c("f.bin"), _c("f.bin.jpg"))],
            id="test_extension_jpg",
        ),
        pytest.param(
            [_c("f.bin"), _c("f.bin.jpeg")],
            [(_c("f.bin"), _c("f.bin.jpeg"))],
            id="test_extension_jpeg",
        ),
        pytest.param(
            [_c("f.bin"), _c("f.bin.pNg")],
            [(_c("f.bin"), _c("f.bin.pNg"))],
            id="test_extension_png_case_insensitivity",
        ),
        pytest.param(
            [_c("f.bin"), _c("f.bin.pNg")],
            [(_c("f.bin"), _c("f.bin.pNg"))],
            id="test_extension_case_insensitivity",
        ),
        pytest.param(
            [_c("a.png")], [(_c("a.png"), _c("a.png"))], id="one_to_one_same_extension"
        ),
        pytest.param(
            [_c("a.bin")], [(_c("a.bin"), _c("a.bin"))], id="one_to_one_other_files"
        ),
        pytest.param(
            [_c("a.bin.png"), _c("a.bin")],
            [(_c("a.bin"), _c("a.bin.png"))],
            id="with_thumb",
        ),
        pytest.param(
            reversed(
                [_c("a.bin.png"), _c("a.bin")],
            ),
            [(_c("a.bin"), _c("a.bin.png"))],
            id="with_thumb_order_does_not_matter",
        ),
        pytest.param(
            [_c("C.bin"), _c("a.bin"), _c("b.bin")],
            [
                (_c("a.bin"), _c("a.bin")),
                (_c("b.bin"), _c("b.bin")),
                (_c("C.bin"), _c("C.bin")),
            ],
            id="one_to_one_multiple_entries",
        ),
        pytest.param(
            [_c("C.bin"), _c("a.bin"), _c("a.bin.jpeg"), _c("b.bin")],
            [
                (_c("a.bin"), _c("a.bin.jpeg")),
                (_c("b.bin"), _c("b.bin")),
                (_c("C.bin"), _c("C.bin")),
            ],
            id="one_to_one_multiple_entries_some_have_thumbnails",
        ),
    ],
)
def test_associate_thumbnails(
    assets_files: list[FileMetaDataGet],
    expected_result: list[tuple[FileMetaDataGet, FileMetaDataGet]],
):
    results = _get_files_with_thumbnails(assets_files)
    assert _get_comparable(results) == _get_comparable(expected_result)
