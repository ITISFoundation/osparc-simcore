from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

import packaging.version
import yaml
from importlib_resources import files
from models_library.services import ServiceDockerData
from pydantic import version

from ...models.schemas.solvers import LATEST_VERSION, Solver

# TODO: move all fake implementation here


@dataclass
class SolversFaker:
    solvers = [
        {
            "id": "3197d0df-1506-351c-86f9-a93783c5c306",
            "name": "simcore/services/comp/opencor",
            "version": "1.0.3",
            "title": "OpenCor",
            "description": "opencor simulator",
            "maintainer": "zhuang@itis.swiss",
        },
        {
            "id": "42838344-03de-4ce2-8d93-589a5dcdfd05",
            "name": "simcore/services/comp/isolve",
            "version": "2.1.1",
            "title": "iSolve",
            "description": "EM solver",
            "maintainer": "info@itis.swiss",
        },
        {
            "id": "e361b455-22c3-329d-a634-f1e5a85ca1dd",
            "name": "simcore/services/comp/isolve",
            "version": "1.0.1",
            "title": "iSolve",
            "description": "EM solver",
            "maintainer": "info@itis.swiss",
        },
    ]

    def get(self, uuid):
        for s in self.solvers:
            if s["id"] == uuid:
                return s
        raise KeyError()

    def get_by_name_and_version(self, name, version):
        try:
            return next(
                s
                for s in self.solvers
                if s["name"].endswith(name) and s["version"] == version
            )
        except StopIteration as err:
            raise KeyError() from err

    def get_all(self, name):
        return [s for s in self.solvers if s["name"].endswith(name)]

    def get_latest(self, name):
        _all = self.get_all(name)
        if not _all:
            raise KeyError()
        return sorted(_all, key=lambda s: packaging.version.parse(s["version"]))[-1]


def load_images() -> Iterator[ServiceDockerData]:
    mocks_dir: Path = files("simcore_service_api_server").joinpath("mocks")
    for filepath in mocks_dir.glob("*.y*ml"):
        image_metadata = yaml.safe_load(filepath.read_text())
        yield ServiceDockerData.parse_obj(image_metadata)


the_fake_impl = SolversFaker()
