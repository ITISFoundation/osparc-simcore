from typing import Optional, Type, TypeVar

from aiohttp import web
from pydantic import BaseModel, ValidationError


def get_request(*args, **kwargs) -> web.BaseRequest:
    """Helper for handler function decorators to retrieve requests"""
    request = kwargs.get("request", args[-1] if args else None)
    if not isinstance(request, web.BaseRequest):
        msg = (
            "Incorrect decorator usage. "
            "Expecting `def handler(request)` "
            "or `def handler(self, request)`."
        )
        raise RuntimeError(msg)
    return request


M = TypeVar("M", bound=BaseModel)


def parse_request_parameters_as(
    parameters_model_cls: Type[M],
    request: web.Request,
    *,
    app_storage_map: Optional[dict[str, str]] = None,
) -> M:
    """Parses request parameters as defined in 'parameters_model_cls' and raises HTTPBadRequest if validation fails

    - 'app_storage_map' maps field name to app's storage key.

    Analogous to pydantic.tools.parse_obj_as()

    NOTE: for the request body, you can proceed as

        body_model = parse_obj_as(ModelGet, await request.json())

    :raises HTTPBadRequest if validation of parameters or queries fail
    :raises ValidationError if app key fails validation
    """
    app_storage_map = app_storage_map or {}
    data = {
        **request.match_info,
        **request.query,
        **{
            field_name: request.app.get(app_key)
            for field_name, app_key in app_storage_map.items()
        },
    }
    try:
        model = parameters_model_cls.parse_obj(data)
        return model

    except ValidationError as e:
        bad_params_errors: list[str] = []
        request_parameters = set(data.keys()) - set(app_storage_map.keys())

        for error in e.errors():
            name = error["loc"][-1]
            if name in request_parameters:
                bad_params_errors.append(
                    f"Invalid {name}='{data[name]}' since {error['msg']} "
                )

        if bad_params_errors:
            raise web.HTTPBadRequest(
                reason=f"Invalid request parameters: {'; '.join(bad_params_errors)}"
            )

        # otherwise is an app value, re-raises err
        raise
