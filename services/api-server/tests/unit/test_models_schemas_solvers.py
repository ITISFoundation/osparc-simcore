from simcore_service_api_server.models.schemas.solvers import SolverImage, Solver

from datetime import datetime


def test_dev():
    img = SolverImage(
        uid="855b8a9c-aa7d-41fa-90d3-ddc0c980d1e5",
        name="simcore/services/comp/isolve",
        title="iSolve",
        maintainer="benkler@speag.com,schild@speag.com",
        released_at=datetime.now(),
    )

    tags = "1.0.3 1.0 mattermost latest".split()

    solver = Solver.create_from_image(img, tags, solvers_url="http://foo.org")

    assert solver.version == tags[0]
    assert solver.version_aliases == tags[1:]
