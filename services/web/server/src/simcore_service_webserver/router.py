""" Main entrypoint to create a server router

"""
# pylint: disable=W0611
from .rest.routing import create_router

__all__ = (
    'create_router'
)
