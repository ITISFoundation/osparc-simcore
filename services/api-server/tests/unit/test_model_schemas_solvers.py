# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from simcore_service_api_server.api.routes.solvers_faker import SolversFaker
from simcore_service_api_server.models.schemas.solvers import Solver


def test_create_solver_from_image_metadata():

    for image_metadata in SolversFaker.load_images():
        solver = Solver.create_from_image(image_metadata)
        print(solver.json(indent=2))

        assert solver.id is not None, "should be auto-generated"
        assert solver.url is None
