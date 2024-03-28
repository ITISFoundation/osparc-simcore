""" Package Metadata

"""

from importlib.metadata import distribution, version

_current_distribution = distribution("simcore-service-dynamic-sidecar")

PROJECT_NAME: str = _current_distribution.metadata["Name"]

API_VERSION: str = version("simcore-service-dynamic-sidecar")
MAJOR, MINOR, PATCH = API_VERSION.split(".")
API_VTAG: str = f"v{MAJOR}"

__version__ = _current_distribution.version


def get_summary() -> str:
    return _current_distribution.metadata.get_all("Summary", [""])[-1]


SUMMARY: str = get_summary()
