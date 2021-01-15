import packaging.version


class FAKE:
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

    @classmethod
    def get(cls, uuid):
        for s in cls.solvers:
            if s["uuid"] == uuid:
                return s
        raise KeyError()

    @classmethod
    def get2(cls, name, version):
        try:
            return next(
                s for s in cls.solvers if s["name"] == name and s["version"] == version
            )
        except StopIteration as err:
            raise KeyError() from err

    @classmethod
    def get_all(cls, name):
        return [s for s in cls.solvers if s["name"] == name]

    @classmethod
    def get_latest(cls, name):
        _all = cls.get_all(name)
        if not _all:
            raise KeyError()
        return sorted(_all, key=lambda s: packaging.version.parse(s["version"]))[-1]
