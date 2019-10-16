""" This sandbox is here to encourange TDD

"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest

from servicelib.utils import URL, Path, resolve_location


def test_resolve_url_location():
    assert isinstance(resolve_location(r"https://www.google.com"), URL)


@pytest.mark.parametrize("path_str", [
    r"~/path/to/file",
    r"./path/relative/to/cwd",
    r"/absolute/path/to/file",
    r"file:///absolute/path/to/file" # Notice that this cannot be get with a session but can be
    ]
)
def test_resolve_path_locations(path_str):
    assert isinstance(resolve_location(path_str), Path)

    assert resolve_location(path_str).is_absolute()
    try:
        uri = resolve_location(path_str).as_uri()
        assert URL(uri).scheme == "file"
    except ValueError:
        pytest.fail("Returned path shall be : https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.as_uri")
