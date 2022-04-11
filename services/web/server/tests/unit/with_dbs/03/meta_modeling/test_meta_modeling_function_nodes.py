# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import collections.abc
import inspect
from typing import get_origin

from simcore_service_webserver.meta_modeling_function_nodes import catalog

# TODO: test i/o schemas on FRONTEND_SERVICES_CATALOG fit the  _fun Callable


def test_frontend_service_to_callable_registry():

    print(f"\n{len(catalog)=}")

    for (node_key, node_version), func in catalog.iter_items():
        if node_call := func.implementation:
            print(" -", node_key, node_version, node_call.__name__)
            assert (
                get_origin(inspect.signature(node_call).return_annotation)
                is collections.abc.Iterator
            ), f"Expected iterable nodes only {(node_key, node_version)=}"
