"""  Utilities to implement _meta.py

"""
from contextlib import suppress

import pkg_resources
from packaging.version import Version
from pkg_resources import Distribution


class PackageInfo:
    """Thin wrapper around pgk_resources.Distribution to access package distribution metadata

    Usage example:

        info: Final = PackageMetaInfo(package_name="simcore-service-library")
        __version__: Final[str] = info.__version__

        PROJECT_NAME: Final[str] = info.project_name
        VERSION: Final[Version] = info.version
        API_VTAG: Final[str] = info.api_prefix_path_tag
        SUMMARY: Final[str] = info.get_summary()

    """

    def __init__(self, package_name: str):
        """
        package_name: as defined in 'setup.name'
        """
        self._distribution: Distribution = pkg_resources.get_distribution(package_name)

    @property
    def project_name(self) -> str:
        return self._distribution.project_name

    @property
    def version(self) -> Version:
        return Version(self._distribution.version)

    @property
    def __version__(self) -> str:
        return self._distribution.version

    @property
    def api_prefix_path_tag(self) -> str:
        """Used as prefix in the api path e.g. 'v0'"""
        return f"v{self.version.major}"

    def get_summary(self) -> str:
        with suppress(Exception):
            try:
                metadata = self._distribution.get_metadata_lines("METADATA")
            except FileNotFoundError:
                metadata = self._distribution.get_metadata_lines("PKG-INFO")

            return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
        return ""

    def get_finished_banner(self) -> str:
        return "{:=^100}".format(
            f"🎉 App {self.project_name}=={self.__version__} shutdown completed 🎉"
        )
