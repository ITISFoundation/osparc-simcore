""" Access to ResourceManager API that give safe access to all data resources distributed with this package


"""
import pathlib
import re
import pkg_resources
import collections
import functools

PkgResourceArgs = collections.namedtuple("PkgResourceArgs", "package_or_requirement resource_name".split())


# TODO: set package_or_requirement. Resources only rely on their name
# TODO: add objects to used resources

# List of pkg_resources functions bound to current package
exists  = functools.partial(pkg_resources.resource_exists, __name__)
stream  = functools.partial(pkg_resources.resource_stream, __name__)
listdir = functools.partial(pkg_resources.resource_listdir, __name__)

def get_path(resource_name):
    resource_path = pathlib.Path( pkg_resources.resource_filename(__name__, resource_name) )
    return resource_path

class ConfigFile:
    """
        Configurtion files installed with this package

        Invariant: all configuration files are identified as `.config/$config_name`
    """
    BASE = '.config'

    def __init__(self, config_name):
        args = self.__create_args(config_name)
        if not pkg_resources.resource_exists(*args):
            raise ValueError("Invalid resource {}:{}".format(*args))

        self._args = args
        self._stream = None

    def __enter__(self):
        self._stream = pkg_resources.resource_stream(*self._args)
        return self._stream

    def __exit__(self, _type, _value, _traceback):
        if self._stream:
            self._stream.close()

    @classmethod
    def __create_args(cls, config_name):
        args = PkgResourceArgs(__name__, '{}/{}'.format(cls.BASE, config_name))
        return args

    @classmethod
    def exists(cls, config_name):
        args = cls.__create_args(config_name)
        return pkg_resources.resource_exists(*args)

    @classmethod
    def list_all(cls):
        PATTERN = re.compile(r'y[a]?ml$')
        config_names = filter(PATTERN.search, pkg_resources.resource_listdir(__name__, cls.BASE))
        return list(config_names)

    @property
    def path(self):
        """
            Returns a path to associated config resource. If package is zipped, it
            will create a temporary copy in cache and return its path
        """
        # See Resource Extraction at http://peak.telecommunity.com/DevCenter/PkgResources#resourcemanager-api
        filepath = pkg_resources.resource_filename(*self._args)
        return pathlib.Path(filepath)
