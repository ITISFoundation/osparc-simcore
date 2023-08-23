# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import types
from typing import get_args, get_origin

from simcore_service_api_server.models.schemas.jobs import ArgumentTypes, File
from simcore_service_api_server.services.solver_job_outputs import (
    BaseFileLink,
    ResultsTypes,
)


def test_resultstypes_and_argument_type_sync():
    # I/O types returned by node-ports must be one-to-one mapped
    # with those returned as output results

    assert get_origin(ArgumentTypes) == types.UnionType
    argument_types_args = set(get_args(ArgumentTypes))

    assert get_origin(ResultsTypes) == types.UnionType
    results_types_args = set(get_args(ResultsTypes))

    # files are in the inputs as File (or Raises KeyError if not)
    argument_types_args.remove(File)

    # files are in the outputs as Links (or Raises KeyError if not)
    results_types_args.remove(BaseFileLink)

    # identical except for File/BaseFileLink
    assert argument_types_args == results_types_args
