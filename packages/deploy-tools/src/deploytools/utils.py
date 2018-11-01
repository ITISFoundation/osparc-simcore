import io
import sys
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional
import os

import yaml


@lru_cache(None)
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent



@lru_cache(None)
def osparc_simcore_root_dir() -> Path:
    """ NOTE: Assumes that installed somewhere below osparc root folder """
    MAX_LEVELS = 6

    def _is_root(dirpath):
        return any(dirpath.glob("services/web/server"))

    root_dir = here().parent.resolve()
    count = 1
    while not _is_root(root_dir) and count < MAX_LEVELS:
        root_dir = root_dir.parent.resolve()
        count +=1

    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert _is_root(root_dir), "%s not look like rootdir" % root_dir
    return root_dir


@lru_cache(None)
def env_devel_file(name: Optional[str]=None) -> Path:
    if name is None:
        name = ".env-devel"
    fpath = osparc_simcore_root_dir() / name

    assert name.startswith("."), name
    assert fpath.exists(), fpath
    return fpath


@lru_cache(None)
def output_dir() -> Path:
    outdir = here() / "../../out"
    outdir = outdir.resolve()
    return outdir


def dump_to_stdout(data: Dict):
    with closing(io.StringIO()) as ios:
        yaml.dump(data, ios, default_flow_style=False)
        print(ios.getvalue()) # pylint: disable=E1101


def dump_to_file(data: Dict, fpath: Path) -> Path:
    os.makedirs(fpath.parent, exist_ok=True)
    with fpath.open('wt') as fh:
        yaml.dump(data, fh, default_flow_style=False)
    return fpath
