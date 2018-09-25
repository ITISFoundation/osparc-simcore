import functools
from pathlib import Path

import pkg_resources
from simcore_service_director import config

RESOURCE_OPENAPI_ROOT = "oas3"
RESOURCE_OPEN_API = "{root}/{version}/openapi.yaml".format(root=RESOURCE_OPENAPI_ROOT, version=config.API_VERSION)
RESOURCE_NODE_SCHEMA = "{root}/{version}/schemas/node-meta-v0.0.1.json".format(root=RESOURCE_OPENAPI_ROOT, version=config.API_VERSION)

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
    resource_path = Path( pkg_resources.resource_filename(__name__, resource_name) )
    return resource_path
