import json
import logging
from pathlib import Path

import httpx
from fastapi.encoders import jsonable_encoder
from httpx._types import URLTypes
from jsonschema import ValidationError
from pydantic import parse_file_as
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel

from .http_calls_capture import get_captured
from .http_calls_capture_processing import CaptureProcessingException

_logger = logging.getLogger(__name__)


class AsyncClientForDevelopmentOnly(httpx.AsyncClient):
    """
    Adds captures mechanism
    """

    def __init__(self, capture_file: Path, **async_clint_kwargs):
        super().__init__(**async_clint_kwargs)
        assert capture_file.name.endswith(
            ".json"
        ), "The capture file should be a json file"
        self._capture_file: Path = capture_file

    async def request(self, method: str, url: URLTypes, **kwargs):
        response: httpx.Response = await super().request(method, url, **kwargs)

        capture_name = f"{method} {url}"
        _logger.info("Capturing %s ... [might be slow]", capture_name)
        try:
            capture: HttpApiCallCaptureModel = get_captured(
                name=capture_name, response=response
            )
            if (
                not self._capture_file.is_file()
                or self._capture_file.read_text().strip() == ""
            ):
                self._capture_file.write_text("[]")
            serialized_captures: list[HttpApiCallCaptureModel] = parse_file_as(
                list[HttpApiCallCaptureModel], self._capture_file
            )
            serialized_captures.append(capture)
            self._capture_file.write_text(
                json.dumps(jsonable_encoder(serialized_captures), indent=1)
            )
        except (CaptureProcessingException, ValidationError, httpx.RequestError):
            _logger.exception(
                "Unexpected failure with %s",
                capture_name,
                exc_info=True,
                stack_info=True,
            )
        return response
