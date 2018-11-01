""" Session submodule

"""
from aiohttp import web

from servicelib.session import get_session
from servicelib.session import setup_session as do_setup_session


def setup(app: web.Application):
    do_setup_session(app)


# alias
setup_session = setup

__all__ = (
    "setup_session",
    "get_session",
)
