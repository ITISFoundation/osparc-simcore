"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
from aiohttp import web


async def list_checkpoints(app: web.Application):
    """ like log history"""
    ...


async def create_checkpoint(app: web.Application):
    ...


async def update_checkpoint(app: web.Application):
    ...


async def get_working_copy(app: web.Application):
    ...


async def checkout(app: web.Application):
    ...


async def get_workbench(app: web.Application):
    ...
