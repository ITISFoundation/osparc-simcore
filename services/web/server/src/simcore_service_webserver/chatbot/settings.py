from aiohttp import web
from pydantic import AnyUrl
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY


class ChatbotSettings(BaseCustomSettings):
    CHATBOT_HOST: AnyUrl
    CHATBOT_PORT: int


def get_plugin_settings(app: web.Application) -> ChatbotSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_CHATBOT
    assert settings, "plugin.setup_chatbot not called?"  # nosec
    assert isinstance(settings, ChatbotSettings)  # nosec
    return settings
