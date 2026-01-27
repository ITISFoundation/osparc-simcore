from typing import Final

from aiohttp import web

from ._confirmation_service import ConfirmationService

CONFIRMATION_SERVICE_APPKEY: Final = web.AppKey("CONFIRMATION_SERVICE", ConfirmationService)
