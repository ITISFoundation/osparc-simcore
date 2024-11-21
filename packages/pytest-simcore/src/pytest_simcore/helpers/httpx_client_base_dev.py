import json
import logging
from pathlib import Path

import httpx
from fastapi.encoders import jsonable_encoder
from httpx._types import URLTypes
from jsonschema import ValidationError
from pydantic import TypeAdapter

from .httpx_calls_capture_errors import CaptureProcessingError
from .httpx_calls_capture_models import HttpApiCallCaptureModel, get_captured_model

_logger = logging.getLogger(__name__)


_HTTP_API_CALL_CAPTURE_MODEL_ADAPTER: TypeAdapter[
    list[HttpApiCallCaptureModel]
] = TypeAdapter(list[HttpApiCallCaptureModel])


class AsyncClientCaptureWrapper(httpx.AsyncClient):
    """
    Adds captures mechanism
    """

    def __init__(self, capture_file: Path, **async_clint_kwargs):
        super().__init__(**async_clint_kwargs)
        if capture_file.is_file():
            assert capture_file.name.endswith(  # nosec
                ".json"
            ), "The capture file should be a json file"
        self._capture_file: Path = capture_file

    async def request(self, method: str, url: URLTypes, **kwargs):
        response: httpx.Response = await super().request(method, url, **kwargs)

        capture_name = f"{method} {url}"
        _logger.info("Capturing %s ... [might be slow]", capture_name)
        try:
            capture: HttpApiCallCaptureModel = get_captured_model(
                name=capture_name, response=response
            )
            if (
                not self._capture_file.is_file()
                or self._capture_file.read_text().strip() == ""
            ):
                self._capture_file.write_text("[]")

            serialized_captures: list[
                HttpApiCallCaptureModel
            ] = _HTTP_API_CALL_CAPTURE_MODEL_ADAPTER.validate_json(
                self._capture_file.read_text()
            )
            serialized_captures.append(capture)
            self._capture_file.write_text(
                json.dumps(
                    jsonable_encoder(
                        serialized_captures,
                        # NOTE: reduces file size by relying on defaults
                        exclude_unset=True,
                        exclude_defaults=True,
                    ),
                    indent=1,
                )
            )
        except (CaptureProcessingError, ValidationError, httpx.RequestError):
            _logger.exception(
                "Unexpected failure with %s",
                capture_name,
                stack_info=True,
            )
        return response
