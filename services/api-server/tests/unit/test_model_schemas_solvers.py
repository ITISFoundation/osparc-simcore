# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pprint

from simcore_service_api_server.api.routes.solvers_faker import load_images
from simcore_service_api_server.models.schemas.solvers import Solver


def test_create_solver_from_image_metadata():
    for image_metadata in load_images():
        solver = Solver.create_from_image(image_metadata)
        pprint(solver)
        assert solver.url is None
