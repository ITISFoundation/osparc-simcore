""" rest - routes mapping based on oaspecs


See tests/test_rest_routing.py for example of usage
"""

import inspect
import logging
from typing import Callable, Dict, Generator, List, Mapping

from aiohttp import web

from .openapi import OpenApiSpec, get_base_path

logger = logging.getLogger(__name__)


def has_handler_signature(fun) -> bool:
    # TODO: last parameter is web.Request or called request?
    return any(param.annotation == web.Request
        for name, param in inspect.signature(fun).parameters.items())


def get_handlers_from_namespace(handlers_nsp) -> Dict:
    """ Gets all handlers in a namespace define by a class or a module

    """
    if inspect.ismodule(handlers_nsp):
        predicate = lambda obj: inspect.isfunction(obj) and has_handler_signature(obj)
    elif hasattr(handlers_nsp, "__class__"):
        predicate = lambda obj: inspect.ismethod(obj) and has_handler_signature(obj)
    else:
        raise ValueError("Expected module or class as namespace, got %s" % type(handlers_nsp))

    name_to_handler_map = dict(inspect.getmembers(handlers_nsp, predicate))
    return name_to_handler_map


def iter_path_operations(specs: OpenApiSpec) -> Generator:
    """Iterates paths in api specs returning tuple (method, path, operation_id)

    NOTE: prepend API version as basepath to path url, e.g. /v0/my/path for path=/my/path
    """
    base_path = get_base_path(specs)

    for url, path in specs.paths.items():
        for method, operation in path.operations.items():
            yield method.upper(), base_path+url, operation.operation_id


def map_handlers_with_operations(
        handlers_map: Mapping[str, Callable],
        operations_it: Generator,
        * ,
        strict: bool=True) -> List[web.RouteDef]:
    """ Matches operation ids with handler names and returns a list of routes

    :param handlers_map: .See get_handlers_from_namespace
    :type handlers_map: Mapping[str, Callable]
    :param operations_it: iterates over specs operations. See iter_path_operations
    :type operations_it: Generator
    :param strict: it raises an error if either a handler or an operator was not mapped, defaults to True
    :param strict: bool, optional
    :raises ValueError: if not operations mapped
    :raises RuntimeError: if not handlers mapped
    :rtype: List[web.RouteDef]
    """

    handlers = dict(handlers_map)
    routes = [ ]
    for method, path, operation_id in operations_it:
        handler = handlers.pop(operation_id, None)
        if handler:
            routes.append( web.route(method.upper(), path, handler, name=operation_id) )
        elif strict:
            raise ValueError("Cannot find any handler named {} ".format(operation_id))

    if handlers and strict:
        raise RuntimeError("{} handlers were not mapped to routes: {}".format(
                len(handlers),
                handlers.keys())
            )

    return routes


def create_routes_from_namespace(
        specs: OpenApiSpec,
        handlers_nsp,
         *,
        strict: bool=True) -> List[web.RouteDef]:
    """ Gets *all* available handlers and maps one-to-one to *all* specs routes

    :param specs: openapi spec object
    :type specs: OpenApiSpec
    :param handlers_nsp: class or module with handler functions
    :param strict: ensures strict mapping, defaults to True
    :param strict: bool, optional
    :rtype: List[web.RouteDef]
    """
    handlers = get_handlers_from_namespace(handlers_nsp)

    if not handlers and strict:
        raise ValueError("No handlers found in %s" % handlers_nsp)

    routes = map_handlers_with_operations(handlers, iter_path_operations(specs), strict=strict)

    return routes
