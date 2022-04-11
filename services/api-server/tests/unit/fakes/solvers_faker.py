from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Callable, Dict, Iterator, Tuple

import packaging.version
import yaml
from fastapi import HTTPException, status
from models_library.services import ServiceDockerData
from simcore_service_api_server.models.schemas.solvers import (
    LATEST_VERSION,
    Solver,
    SolverKeyId,
    VersionStr,
)

SKey = Tuple[SolverKeyId, VersionStr]


@dataclass
class SolversFaker:

    solvers: Dict[SKey, Solver]

    def get(self, key, *, url=None) -> Solver:
        return self.solvers[key].copy(update={"url": url})

    def values(self, url_resolver: Callable) -> Iterator[Solver]:
        for s in self.solvers.values():
            yield s.copy(update={"url": url_resolver(s)})

    def get_by_name_and_version(
        self, name: str, version: str, url_resolver: Callable
    ) -> Solver:
        try:
            return next(
                s.copy(update={"url": url_resolver(s.id)})
                for s in self.solvers.values()
                if s.id.endswith(name) and s.version == version
            )
        except StopIteration as err:
            raise KeyError() from err

    def get_latest(self, name: str, url_resolver: Callable) -> Solver:
        _all = list(s for s in self.solvers.values() if s.id.endswith(name))
        latest = sorted(_all, key=lambda s: packaging.version.parse(s.version))[-1]
        return latest.copy(update={"url": url_resolver(latest.id)})

    @classmethod
    def load_images(cls) -> Iterator[ServiceDockerData]:
        mocks_dir: Path = files("simcore_service_api_server").joinpath("mocks")
        for filepath in mocks_dir.glob("*.y*ml"):
            image = yaml.safe_load(filepath.read_text())
            yield ServiceDockerData.parse_obj(image)

    @classmethod
    def solver_items(cls) -> Iterator[Tuple[SKey, Solver]]:
        for image in cls.load_images():
            solver = Solver.create_from_image(image)
            yield (solver.id, solver.version), solver

    @classmethod
    def create_from_mocks(cls) -> "SolversFaker":
        return cls(solvers=dict(cls.solver_items()))


the_fake_impl = SolversFaker.create_from_mocks()


# /files API fake implementations

# GET /solvers


async def list_solvers(
    url_for: Callable,
):
    def _url_resolver(solver: Solver):
        return url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return list(the_fake_impl.values(_url_resolver))


async def get_solver_by_name_and_version(
    solver_name: SolverKeyId,
    version: VersionStr,
    url_for: Callable,
):
    try:
        print(f"/{solver_name}/{version}", flush=True)

        def _url_resolver(solver: Solver):
            return url_for(
                "get_solver_release", solver_key=solver.id, version=solver.version
            )

        if version == LATEST_VERSION:
            solver = the_fake_impl.get_latest(solver_name, _url_resolver)
        else:
            solver = the_fake_impl.get_by_name_and_version(
                solver_name, version, _url_resolver
            )
        return solver

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_name}:{version} not found",
        ) from err


async def get_solver(
    solver_name: SolverKeyId,
    version: VersionStr,
    url_for: Callable,
):
    try:
        solver = the_fake_impl.get(
            (solver_name, version),
            url=url_for("get_solver_release", solver_key=solver_name, version=version),
        )
        return solver

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_name}:{version} not found",
        ) from err
