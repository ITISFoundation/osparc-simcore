""" rest - middlewares for error, enveloping and validation


"""
import logging

from aiohttp import web
from openapi_core.schema.exceptions import OpenAPIError

from .rest_models import ErrorItemType, ErrorType, LogMessageType
from .rest_responses import (JSON_CONTENT_TYPE, create_data_response,
                             create_error_response, is_enveloped_from_text, is_enveloped_from_map, wrap_as_envelope)
from .rest_utils import EnvelopeFactory
from .rest_validators import OpenApiValidator
import json


DEFAULT_API_VERSION = "v0"


logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return request.path.startswith(base_path)


def _process_and_raise_unexpected_error(err):
    # TODO: send info + trace to client ONLY in debug mode!!!
    logger.exception("Unexpected exception on server side")
    exc = create_error_response(
            [err,],
            "Unexpected Server error",
            web.HTTPInternalServerError
        )
    raise exc


def error_middleware_factory(api_version: str = DEFAULT_API_VERSION):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Ensure all error raised are properly enveloped and json responses
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # FIXME: review when to send info to client and when not!
        try:
            response = await handler(request)
            return response

        except web.HTTPError as err:
            # TODO: differenciate between server/client error
            if not err.reason:
                err.reason = "Unexpected error"

            err.content_type = JSON_CONTENT_TYPE

            if not err.text or not is_enveloped_from_text(err.text):
                error = ErrorType(
                    errors=[ErrorItemType.from_error(err), ],
                    status=err.status,
                    logs=[LogMessageType(message=err.reason, level="ERROR"), ]
                )
                err.text = EnvelopeFactory(error=error).as_text()

            raise

        except web.HTTPSuccessful as ex:
            ex.content_type = JSON_CONTENT_TYPE
            if ex.text:
                try:
                    payload = json.loads(ex.text)
                    if not is_enveloped_from_map(payload):
                        payload = wrap_as_envelope(data=payload)
                        ex.text = json.dumps(payload)
                except Exception as err:  # pylint: disable=W0703
                    _process_and_raise_unexpected_error(err)
            raise ex

        except web.HTTPRedirection as ex:
            logger.debug("Redirection %s", ex)
            raise

        except Exception as err:  # pylint: disable=W0703
            _process_and_raise_unexpected_error(err)

    return _middleware


def validate_middleware_factory(api_version: str = DEFAULT_API_VERSION):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Validates requests against openapi specs and extracts body, params, etc ...
            Validate response against openapi specs
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # TODO: move this outside!
        RQ_VALIDATED_DATA_KEYS = (
            "validated-path", "validated-query", "validated-body")

        try:
            validator = OpenApiValidator.create(request.app, api_version)

            # FIXME: if request is HTTPNotFound, it still goes through middlewares and then validator.check_request fails!!!
            try:
                path, query, body = await validator.check_request(request)

                # TODO: simplify!!!!
                # Injects validated
                request["validated-path"] = path
                request["validated-query"] = query
                request["validated-body"] = body
            except OpenAPIError:
                raise
            except Exception: # pylint: disable=W0703
                pass

            response = await handler(request)

            # FIXME:  openapi-core fails to validate response when specs are in separate files!
            validator.check_response(response)

        finally:
            for k in RQ_VALIDATED_DATA_KEYS:
                request.pop(k, None)

        return response

    return _middleware


def envelope_middleware_factory(api_version: str = DEFAULT_API_VERSION):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Ensures all responses are enveloped as {'data': .. , 'error', ...} in json
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        resp = await handler(request)

        if not isinstance(resp, web.Response):
            response = create_data_response(data=resp)
        else:
            # Enforced by user. Should check it is json?
            response = resp
        return response
    return _middleware


def append_rest_middlewares(app: web.Application, api_version: str = DEFAULT_API_VERSION):
    """ Helper that appends rest-middlewares in the correct order

    """
    app.middlewares.append(error_middleware_factory(api_version))
    # FIXME:  openapi-core fails to validate response when specs are in separate files!
    # FIXME: disabled so webserver and storage do not get this issue
    #app.middlewares.append(validate_middleware_factory(api_version))
    app.middlewares.append(envelope_middleware_factory(api_version))
