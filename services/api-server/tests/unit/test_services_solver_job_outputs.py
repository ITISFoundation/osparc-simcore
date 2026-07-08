# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import types
from typing import Union, get_args, get_origin

from simcore_service_api_server.models.schemas.jobs import ArgumentTypes, File
from simcore_service_api_server.services_http.solver_job_outputs import (
    BaseFileLink,
    ResultsTypes,
)


def test_resultstypes_and_argument_type_sync():
    # I/O types returned by node-ports must be one-to-one mapped
    # with those returned as output results

    # Python 3.12+ `type` statement creates TypeAliasType; unwrap with __value__
    argument_types = ArgumentTypes.__value__ if hasattr(ArgumentTypes, "__value__") else ArgumentTypes
    assert get_origin(argument_types) in (types.UnionType, Union)
    argument_types_args = set(get_args(argument_types))

    results_types = ResultsTypes.__value__ if hasattr(ResultsTypes, "__value__") else ResultsTypes
    assert get_origin(results_types) in (types.UnionType, Union)
    results_types_args = set(get_args(results_types))

    # files are in the inputs as File (or Raises KeyError if not)
    argument_types_args.remove(File)

    # files are in the outputs as Links (or Raises KeyError if not)
    results_types_args.remove(BaseFileLink)

    # identical except for File/BaseFileLink
    assert argument_types_args == results_types_args
