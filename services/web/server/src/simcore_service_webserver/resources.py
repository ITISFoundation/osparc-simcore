""" Safe access to all data resources distributed with this package

See https://setuptools.readthedocs.io/en/latest/pkg_resources.html
"""
import pathlib
import pkg_resources
import functools


# resources names
RESOURCE_OPENAPI = "oas3"
RESOURCE_CONFIG  = "config"

"""
 List of pkg_resources functions *bound* to current package with the following signature

   function(resource_name)

 Note that resource names must be /-separated paths and
 cannot be absolute (i.e. no leading /) or contain relative names like "..".
 Do not use os.path routines to manipulate resource paths, as they are not filesystem paths.

 Resources are read/only files/folders
"""
exists  = functools.partial(pkg_resources.resource_exists, __name__)
stream  = functools.partial(pkg_resources.resource_stream, __name__)
listdir = functools.partial(pkg_resources.resource_listdir, __name__)
isdir = functools.partial(pkg_resources.resource_isdir, __name__)


def get_path(resource_name):
    """ Returns a path to a resource

        WARNING: existence of file is not guaranteed. Use resources.exists
        WARNING: resource files are supposed to be used as read-only!
    """
    resource_path = pathlib.Path( pkg_resources.resource_filename(__name__, resource_name) )
    return resource_path
