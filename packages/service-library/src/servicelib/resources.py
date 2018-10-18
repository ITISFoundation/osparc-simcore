""" Safe access to all data resources distributed with this package

See https://setuptools.readthedocs.io/en/latest/pkg_resources.html
"""
import pathlib
import pkg_resources
from pathlib import Path
#import typing
import attr


@attr.s(frozen=True, auto_attribs=True)
class ResourcesFacade:
    """ Facade to access data resources installed with a distribution

        - Built on top of pkg_resources

        Resources are read-only files/folders
    """
    package_name: str
    distribution_name: str
    config_folder: str

    def exists(self, resource_name: str):
        return pkg_resources.resource_exists(self.package_name, resource_name)

    def stream(self, resource_name: str):
        return pkg_resources.resource_stream(self.package_name, resource_name)

    def listdir(self, resource_name: str):
        return pkg_resources.resource_listdir(self.package_name, resource_name)

    def isdir(self, resource_name: str):
        return pkg_resources.resource_isdir(self.package_name, resource_name)

    def get_path(self, resource_name: str) -> Path:
        """ Returns a path to a resource

            WARNING: existence of file is not guaranteed. Use resources.exists
            WARNING: resource files are supposed to be used as read-only!
        """
        resource_path = pathlib.Path( pkg_resources.resource_filename(self.package_name, resource_name) )
        return resource_path

    def get_distribution(self):
        """ Returns distribution info object """
        return pkg_resources.get_distribution(self.distribution_name)
