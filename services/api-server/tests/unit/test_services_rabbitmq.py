# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import FastAPI
from simcore_service_api_server.services.rabbitmq import (
    get_rabbitmq_client,
    setup_rabbitmq,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


def test_it(app: FastAPI):

    setup_rabbitmq(app)

    rabbit_client = get_rabbitmq_client(app)
