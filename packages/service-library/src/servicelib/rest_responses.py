"""

FIXME: these are prototype! do not use in production
"""
from typing import Dict, Mapping, Tuple

import attr
from aiohttp import web

from .rest_models import LogMessageType
from .rest_codecs import jsonify
from .rest_models import ErrorItemType, ErrorType

ENVELOPE_KEYS = ('data', 'error')
JSON_CONTENT_TYPE = 'application/json'

def is_enveloped_from_map(payload: Mapping) -> bool:
    return all(k in ENVELOPE_KEYS for k in payload.keys())


def is_enveloped(payload) -> bool:
    if isinstance(payload, Mapping):
        return is_enveloped_from_map(payload)
    return False

def wrap_as_envelope(data=None, error=None, as_null=True):
    """
    as_null: if True, keys for null values are created and assigned to None
    """
    payload = {}
    if data or as_null:
        payload['data'] = data
    if error or as_null:
        payload['error'] = error
    return payload


def unwrap_envelope(payload: Dict) -> Tuple:
    """
        Safe returns (data, error) tuple from a response payload
    """
    return tuple(payload.get(k) for k in ENVELOPE_KEYS) if payload else (None, None)



def create_data_response(data) -> web.Response:
    response = None
    try:
        if not is_enveloped(data):
            payload = wrap_as_envelope(data)
        else:
            payload = data

        response = web.json_response(payload, dumps=jsonify)
    except (TypeError, ValueError) as err:
        # TODO: assumes openapi error model!!!
        error = ErrorType(
            errors=[ErrorItemType.from_error(err), ],
            status=web.HTTPInternalServerError.status_code
        )
        response = web.HTTPInternalServerError(
            reason = str(err),
            text= jsonify(attr.asdict(error)),
            content_type=JSON_CONTENT_TYPE
        )
    return response


def log_response(msg: str, level: str) -> web.Response:
    """ Produces an enveloped response with a log message

    Analogous to  aiohttp's web.json_response
    """
    # TODO: link more with real logger
    msg = LogMessageType(msg, level)
    response = web.json_response(data={
        'data': attr.asdict(msg),
        'error': None
    })
    return response


__all__ = (
    'unwrap_envelope',
    'log_response'
)
