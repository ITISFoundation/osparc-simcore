from functools import cached_property

from aiohttp import web
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import MixinServiceSettings, URLPart

from ..application_keys import APP_SETTINGS_APPKEY


class ChatbotSettings(BaseCustomSettings, MixinServiceSettings):
    CHATBOT_HOST: str
    CHATBOT_PORT: int

    @cached_property
    def base_url(self) -> str:
        # http://chatbot:8000
        return self._compose_url(
            prefix="CHATBOT",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )


def get_plugin_settings(app: web.Application) -> ChatbotSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_CHATBOT
    assert settings, "plugin.setup_chatbot not called?"  # nosec
    assert isinstance(settings, ChatbotSettings)  # nosec
    return settings
