"""

FIXME: these are prototype! do not use in production
"""

import json  # TODO: add ujson
from typing import Dict, Mapping, Tuple

import attr
from aiohttp import web

from .rest_models import LogMessageType

ENVELOPE_KEYS = ('data', 'error')


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


#def wrap_envelope(*, data=None, error=None) -> Dict:
#    raise NotImplementedError("")
#    # TODO should convert data, error to dicts!


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
