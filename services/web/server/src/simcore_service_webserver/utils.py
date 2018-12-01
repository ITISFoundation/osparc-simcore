"""
    General utilities and helper functions
"""
import hashlib
import os
import sys
from pathlib import Path
from typing import Iterable, List

from aiohttp.web import HTTPFound
from yarl import URL

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

def is_osparc_repo_dir(path: Path) -> bool:
    # TODO: implement with git cli
    expected = (".github", "packages", "services")
    got = [p.name for p in path.iterdir() if p.is_dir()]
    return all(d in got for d in expected)

def search_osparc_repo_dir():
    """ Returns path to root repo dir or None

        NOTE: assumes this file within repo, i.e. only happens in edit mode!
    """
    MAX_ITERATIONS = 8
    root_dir = CURRENT_DIR
    if "services/web/server" in str(root_dir):
        it = 1
        while not is_osparc_repo_dir(root_dir) and it<MAX_ITERATIONS:
            root_dir = root_dir.parent
            it += 1

        if is_osparc_repo_dir(root_dir):
            return root_dir
    return None


def as_list(obj) -> List:
    if isinstance(obj, Iterable):
        return list(obj)
    return [obj,]

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


def gravatar_hash(email):
    return hashlib.md5(email.lower().encode('utf-8')).hexdigest()

def gravatar_url(gravatarhash, size=100, default='identicon', rating='g') -> URL:
    url = URL('https://secure.gravatar.com/avatar/%s' % gravatarhash)
    return url.with_query(s=size, d=default, r=rating)

__all__ = (
    'redirect',
)
