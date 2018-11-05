# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import attr
from aiohttp import web


@attr.s(auto_attribs=True)
class Data:
    x: int=3
    y: str="foo"


class Handlers:
    def get_dict(self, request: web.Request):
        return {'x':3, 'y':"3"}

    def get_envelope(self, request: web.Request):
        data = {'x':3, 'y':"3"}
        return {"error": None, "data": data}

    def get_list(self, request: web.Request):
        return [ {'x':3, 'y':"3"} ]*3

    def get_attobj(self, request: web.Request):
        return Data(3, "3")

    def get_string(self, request: web.Request):
        return "foo"

    def get_number(self, request: web.Request):
        return 3

    def get_mixed(self, request: web.Request):
        data = [ {'x':3, 'y':"3", 'z':[Data(1, "3"), ]*2} ]*3
        return data
