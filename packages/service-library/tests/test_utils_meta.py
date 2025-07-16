from typing import Final

import pytest
from models_library.basic_types import VersionStr
from packaging.version import Version
from pytest_mock import MockerFixture
from servicelib.utils_meta import PackageInfo


def test_meta_module_implementation():
    # This is what is used in _meta.py

    info: Final = PackageInfo(package_name="simcore-service-library")
    __version__: Final[VersionStr] = info.__version__

    PROJECT_NAME: Final[str] = info.project_name
    VERSION: Final[Version] = info.version
    API_VTAG: Final[str] = info.api_prefix_path_tag
    SUMMARY: Final[str] = info.get_summary()

    APP_FINISHED_BANNER_MSG = info.get_finished_banner()

    # validation
    assert isinstance(PROJECT_NAME, str)
    assert isinstance(VERSION, Version)

    assert __version__ == f"{VERSION}"

    assert API_VTAG.startswith("v")
    assert f"{VERSION.major}" in API_VTAG
    assert "/" not in API_VTAG

    assert any(SUMMARY)

    assert __version__ in APP_FINISHED_BANNER_MSG
    assert PROJECT_NAME in APP_FINISHED_BANNER_MSG


@pytest.mark.parametrize(
    "package_name, app_name, is_valid_app_name, is_correct_app_name",
    [
        ("simcore-service-library", "simcore-service-library", True, True),
        ("simcore-service-lib", "simcore-service-library", True, True),
        ("simcore_service_library", "simcore_service_library", False, True),
    ],
)
def test_app_name(
    mocker: MockerFixture,
    package_name: str,
    app_name: str,
    is_valid_app_name: bool,
    is_correct_app_name: bool,
):

    mocker.patch(
        "servicelib.utils_meta.distribution",
        return_value=mocker.Mock(metadata={"Name": app_name, "Version": "1.0.0"}),
    )
    if is_valid_app_name:
        info = PackageInfo(package_name=package_name)
        if is_correct_app_name:
            assert info.app_name == app_name
    else:
        with pytest.raises(ValueError):
            _ = PackageInfo(package_name=package_name)
