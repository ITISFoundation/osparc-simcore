"""  Utilities to implement _meta.py

"""

from importlib.metadata import distribution

from models_library.basic_types import VersionStr
from packaging.version import Version
from pydantic import TypeAdapter


class PackageInfo:
    """Thin wrapper around pgk_resources.Distribution to access package distribution metadata

    Usage example:

        info: Final = PackageMetaInfo(package_name="simcore-service-library")
        __version__: Final[VersionStr] = info.__version__

        PROJECT_NAME: Final[str] = info.project_name
        VERSION: Final[Version] = info.version
        API_VTAG: Final[str] = info.api_prefix_path_tag
        SUMMARY: Final[str] = info.get_summary()

    """

    def __init__(self, package_name: str):
        """
        package_name: as defined in 'setup.name'
        """
        self._distribution = distribution(package_name)

    @property
    def project_name(self) -> str:
        return self._distribution.metadata["Name"]

    @property
    def version(self) -> Version:
        return Version(self._distribution.version)

    @property
    def __version__(self) -> VersionStr:
        return TypeAdapter(VersionStr).validate_python(self._distribution.version)

    @property
    def api_prefix_path_tag(self) -> str:
        """Used as prefix in the api path e.g. 'v0'"""
        return f"v{self.version.major}"

    def get_summary(self) -> str:
        return self._distribution.metadata.get_all("Summary", [""])[-1]

    def get_finished_banner(self) -> str:
        return "{:=^100}".format(
            f"🎉 App {self.project_name}=={self.__version__} shutdown completed 🎉"
        )
