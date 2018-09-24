"""
    General utilities and helper functions
"""
import os
import sys
from aiohttp.web import HTTPFound

CDIR = os.path.dirname(sys.argv[0] if __name__ == '__main__' else __file__)


def import_with_retry(module_name, *extended_paths):
    """
        Imports module_name and if it fails, it retries
        but including extended_path in the sys.path
    """
    import importlib
    module = None
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        snapshot = list(sys.path)
        try:
            sys.path = list(extended_paths) + sys.path
            module = importlib.import_module(module_name)
        except ImportError:
            sys.path = snapshot
            # TODO: should I remove from sys.path even if it does not fail?

    return module


def get_thrift_api_folders(startdir):
    """ Returns all directory paths that match 'startdir/**/gen-py'

        This is the folder layout produced by the thrift generator
        TODO: deprecate this function
    """
    folders = []
    for root, dirs, _ in os.walk(startdir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        if "gen-py" in dirs:
            dirs[:] = []  # stop looking under this node
            folders.append(os.path.join(root, "gen-py"))
    return folders


def redirect(*args, **kwargs):
    raise HTTPFound(*args, **kwargs)


__all__ = (
    'redirect',
)
