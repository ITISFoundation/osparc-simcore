import datetime
from uuid import uuid4

import pytest
from models_library.api_schemas_storage import FileMetaDataGet
from simcore_service_webserver.projects._nodes_api import (
    _SUPPORTED_PREVIEW_FILE_EXTENSIONS,
    _FileWithThumbnail,
    _get_files_with_thumbnails,
)

_PROJECT_ID = uuid4()
_NODE_ID = uuid4()
_UTC_NOW = datetime.datetime.now(tz=datetime.UTC)


def _c(file_name: str) -> FileMetaDataGet:
    """simple converter utility"""
    return FileMetaDataGet.model_validate(
        {
            "file_uuid": f"{_PROJECT_ID}/{_NODE_ID}/{file_name}",
            "location_id": 0,
            "file_name": file_name,
            "file_id": f"{_PROJECT_ID}/{_NODE_ID}/{file_name}",
            "created_at": _UTC_NOW,
            "last_modified": _UTC_NOW,
        },
    )


def _get_comparable(entries: list[_FileWithThumbnail]) -> set[tuple[str, str]]:
    return {(x.file.file_id, x.thumbnail.file_id) for x in entries}


@pytest.mark.parametrize(
    "assets_files, expected_result",
    [
        pytest.param(
            [_c("f.gltf"), _c("f.gltf.png")],
            [_FileWithThumbnail(_c("f.gltf"), _c("f.gltf.png"))],
            id="test_extension_gltf",
        ),
        pytest.param(
            [_c("f.gltf"), _c("f.gltf.jpg")],
            [_FileWithThumbnail(_c("f.gltf"), _c("f.gltf.jpg"))],
            id="test_extension_jpg",
        ),
        pytest.param(
            [_c("f.gltf"), _c("f.gltf.jpeg")],
            [_FileWithThumbnail(_c("f.gltf"), _c("f.gltf.jpeg"))],
            id="test_extension_jpeg",
        ),
        pytest.param(
            [_c("f.gltf"), _c("f.gltf.pNg")],
            [_FileWithThumbnail(_c("f.gltf"), _c("f.gltf.pNg"))],
            id="test_extension_png_case_insensitivity",
        ),
        pytest.param(
            [_c("f.gltf"), _c("f.gltf.pNg")],
            [_FileWithThumbnail(_c("f.gltf"), _c("f.gltf.pNg"))],
            id="test_extension_case_insensitivity",
        ),
        pytest.param(
            [_c("a.png")],
            [_FileWithThumbnail(_c("a.png"), _c("a.png"))],
            id="one_to_one_same_extension",
        ),
        pytest.param(
            [_c("a.gltf")],
            [_FileWithThumbnail(_c("a.gltf"), _c("a.gltf"))],
            id="one_to_one_other_files",
        ),
        pytest.param(
            [_c("a.gltf.png"), _c("a.gltf")],
            [_FileWithThumbnail(_c("a.gltf"), _c("a.gltf.png"))],
            id="with_thumb",
        ),
        pytest.param(
            reversed(
                [_c("a.gltf.png"), _c("a.gltf")],
            ),
            [_FileWithThumbnail(_c("a.gltf"), _c("a.gltf.png"))],
            id="with_thumb_order_does_not_matter",
        ),
        pytest.param(
            [_c("C.gltf"), _c("a.gltf"), _c("b.gltf")],
            [
                _FileWithThumbnail(_c("a.gltf"), _c("a.gltf")),
                _FileWithThumbnail(_c("b.gltf"), _c("b.gltf")),
                _FileWithThumbnail(_c("C.gltf"), _c("C.gltf")),
            ],
            id="one_to_one_multiple_entries",
        ),
        pytest.param(
            [_c("C.gltf"), _c("a.gltf"), _c("a.gltf.jpeg"), _c("b.gltf")],
            [
                _FileWithThumbnail(_c("a.gltf"), _c("a.gltf.jpeg")),
                _FileWithThumbnail(_c("b.gltf"), _c("b.gltf")),
                _FileWithThumbnail(_c("C.gltf"), _c("C.gltf")),
            ],
            id="one_to_one_multiple_entries_some_have_thumbnails",
        ),
        pytest.param(
            [_c(f"a{x}") for x in _SUPPORTED_PREVIEW_FILE_EXTENSIONS],
            [
                _FileWithThumbnail(_c(f"a{x}"), _c(f"a{x}"))
                for x in _SUPPORTED_PREVIEW_FILE_EXTENSIONS
            ],
            id="all_supported_extensions_detected",
        ),
    ],
)
def test_associate_thumbnails(
    assets_files: list[FileMetaDataGet],
    expected_result: list[_FileWithThumbnail],
):
    results = _get_files_with_thumbnails(assets_files)
    assert _get_comparable(results) == _get_comparable(expected_result)
