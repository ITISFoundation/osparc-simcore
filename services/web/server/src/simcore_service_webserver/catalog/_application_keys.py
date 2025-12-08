from typing import Final

from aiohttp import web
from pint import UnitRegistry

UNIT_REGISTRY_APPKEY: Final = web.AppKey("UNIT_REGISTRY_APPKEY", UnitRegistry)
