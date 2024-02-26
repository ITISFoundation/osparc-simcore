""" Safe access to all data resources distributed with this package

See https://setuptools.readthedocs.io/en/latest/pkg_resources.html
"""

import pathlib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class DataResourcesFacade:
    """Facade to access data resources installed with a distribution

    - Built on top of pkg_resources

    Resources are read-only files/folders
    """

    package_name: str
    distribution_name: str

    def exists(self, resource_name: str) -> bool:
        path = self.get_path(resource_name)

        return path.exists()

    def get_path(self, resource_name: str) -> Path:
        """Returns a path to a resource

        WARNING: existence of file is not guaranteed
        WARNING: resource files are supposed to be used as read-only!
        """
        ref = files(self.package_name) / resource_name
        return pathlib.Path(f"{ref}")


# resources env keys
CPU_RESOURCE_LIMIT_KEY = "SIMCORE_NANO_CPUS_LIMIT"
MEM_RESOURCE_LIMIT_KEY = "SIMCORE_MEMORY_BYTES_LIMIT"
