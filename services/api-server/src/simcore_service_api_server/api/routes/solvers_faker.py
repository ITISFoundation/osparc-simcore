from dataclasses import dataclass

import packaging.version


@dataclass
class SolversFaker:
    solvers = [
        {
            "uuid": "3197d0df-1506-351c-86f9-a93783c5c306",
            "name": "simcore/services/comp/opencor",
            "version": "1.0.3",
            "title": "OpenCor",
            "description": "opencor simulator",
            "maintainer": "mapcore@nz",
        },
        {
            "uuid": "42838344-03de-4ce2-8d93-589a5dcdfd05",
            "name": "simcore/services/comp/isolve",
            "version": "2.1.1",
            "title": "iSolve",
            "description": "EM solver",
            "maintainer": "info@itis.swiss",
        },
        {
            "uuid": "e361b455-22c3-329d-a634-f1e5a85ca1dd",
            "name": "simcore/services/comp/isolve",
            "version": "1.0.1",
            "title": "iSolve",
            "description": "EM solver",
            "maintainer": "info@itis.swiss",
        },
    ]

    def get(self, uuid):
        for s in self.solvers:
            if s["uuid"] == uuid:
                return s
        raise KeyError()

    def get2(self, name, version):
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


the_fake_impl = SolversFaker()
