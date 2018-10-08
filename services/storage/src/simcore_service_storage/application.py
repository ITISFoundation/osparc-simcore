""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a configuration object
"""
import logging

from aiohttp import web

log = logging.getLogger(__name__)

def create(config):
    log.debug("Initializing ... ")
    app = web.Application()

    return app

def run(config, app=None):
    log.debug("Serving app ... ")
    if not app:
        app = create(config)

    web.run_app(app, 
        host=config["main"]["host"], 
        port=config["main"]["port"])
