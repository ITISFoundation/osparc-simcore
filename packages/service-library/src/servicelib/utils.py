""" General utils

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""
from pathlib import Path


def is_osparc_repo_dir(path: Path) -> bool:
    # TODO: implement with git cli
    expected = (".github", "packages", "services")
    got = [p.name for p in path.iterdir() if p.is_dir()]
    return all(d in got for d in expected)


def search_osparc_repo_dir(start, max_iterations=8):
    """ Returns path to root repo dir or None if it does not exists

        NOTE: assumes starts is a path within repo
    """
    max_iterations = max(max_iterations, 1)
    root_dir = Path(start)
    iteration_number = 0
    while not is_osparc_repo_dir(root_dir) and iteration_number<max_iterations:
        root_dir = root_dir.parent
        iteration_number += 1

    return root_dir if is_osparc_repo_dir(root_dir) else None
