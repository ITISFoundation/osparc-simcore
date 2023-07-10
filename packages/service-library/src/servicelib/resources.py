""" Safe access to all data resources distributed with this package

See https://setuptools.readthedocs.io/en/latest/pkg_resources.html
"""
import pathlib
from dataclasses import dataclass
from pathlib import Path

import pkg_resources


@dataclass(frozen=True)
class DataResourcesFacade:
    """Facade to access data resources installed with a distribution

    - Built on top of pkg_resources

    Resources are read-only files/folders
    """

    package_name: str
    distribution_name: str

    def exists(self, resource_name: str) -> bool:
        return pkg_resources.resource_exists(self.package_name, resource_name)

    def get_path(self, resource_name: str) -> Path:
        """Returns a path to a resource

        WARNING: existence of file is not guaranteed
        WARNING: resource files are supposed to be used as read-only!
        """
        return pathlib.Path(
            pkg_resources.resource_filename(self.package_name, resource_name)
        )


# resources env keys
CPU_RESOURCE_LIMIT_KEY = "SIMCORE_NANO_CPUS_LIMIT"
MEM_RESOURCE_LIMIT_KEY = "SIMCORE_MEMORY_BYTES_LIMIT"
