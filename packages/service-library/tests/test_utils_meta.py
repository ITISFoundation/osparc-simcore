from typing import Final

from packaging.version import Version
from servicelib.utils_meta import PackageInfo


def test_meta_module_implementation():
    # This is what is used in _meta.py

    info: Final = PackageInfo(package_name="simcore-service-library")
    __version__: Final[str] = info.__version__

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
    assert any(APP_FINISHED_BANNER_MSG)
