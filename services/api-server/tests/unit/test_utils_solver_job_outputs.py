# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from simcore_service_api_server.models.schemas.jobs import ArgumentType, File
from simcore_service_api_server.utils.solver_job_outputs import (
    BaseFileLink,
    ResultsTypes,
)
from simcore_service_api_server.utils.typing_extra import get_types


def test_result_type_mapped():
    # I/O types returned by node-ports must be one-to-one mapped
    # with those returned as output results

    api_arg_types = list(get_types(ArgumentType))
    output_arg_types = list(get_types(ResultsTypes))

    assert File in api_arg_types
    assert BaseFileLink in output_arg_types

    api_arg_types.remove(File)
    output_arg_types.remove(BaseFileLink)

    assert set(api_arg_types) == set(output_arg_types)
