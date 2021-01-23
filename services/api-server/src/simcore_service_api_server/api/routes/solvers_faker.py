from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, Tuple
from uuid import UUID

import packaging.version
import yaml
from importlib_resources import files
from models_library.services import ServiceDockerData

from ...models.schemas.solvers import Solver


@dataclass
class SolversFaker:

    solvers: Dict[UUID, Solver]

    def get(self, uuid, *, url=None) -> Solver:
        return self.solvers[uuid].copy(update={"url": url})

    def values(self, url_resolver: Callable) -> Iterator[Solver]:
        for s in self.solvers.values():
            yield s.copy(update={"url": url_resolver(s.id)})

    def get_by_name_and_version(
        self, name: str, version: str, url_resolver: Callable
    ) -> Solver:
        try:
            return next(
                s.copy(update={"url": url_resolver(s.id)})
                for s in self.solvers.values()
                if s.name.endswith(name) and s.version == version
            )
        except StopIteration as err:
            raise KeyError() from err

    def get_latest(self, name: str, url_resolver: Callable) -> Solver:
        _all = list(s for s in self.solvers.values() if s.name.endswith(name))
        latest = sorted(_all, key=lambda s: packaging.version.parse(s.version))[-1]
        return latest.copy(update={"url": url_resolver(latest.id)})

    @classmethod
    def load_images(cls) -> Iterator[ServiceDockerData]:
        mocks_dir: Path = files("simcore_service_api_server").joinpath("mocks")
        for filepath in mocks_dir.glob("*.y*ml"):
            image = yaml.safe_load(filepath.read_text())
            yield ServiceDockerData.parse_obj(image)

    @classmethod
    def solver_items(cls) -> Iterator[Tuple[UUID, Solver]]:
        for image in cls.load_images():
            solver = Solver.create_from_image(image)
            yield solver.id, solver

    @classmethod
    def create_from_mocks(cls) -> "SolversFaker":
        return cls(solvers=dict(cls.solver_items()))


the_fake_impl = SolversFaker.create_from_mocks()
