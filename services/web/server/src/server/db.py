""" Postgress db
"""
import logging

import aiopg.sa

_LOGGER = logging.getLogger(__name__)

class RecordNotFound(Exception):
    """Requested record in database was not found"""

async def create_aiopg(app):
    _LOGGER.debug('creating db engine ... ')

    conf = app['config']['postgres']
    engine = await aiopg.sa.create_engine(
        database=conf['database'],
        user=conf['user'],
        password=conf['password'],
        host=conf['host'],
        port=conf['port'],
        minsize=conf['minsize'],
        maxsize=conf['maxsize'],
    )
    
    _LOGGER.debug('db engine created')
    app['db_engine'] = engine

    _LOGGER.debug('db engine created')


async def dispose_aiopg(app):
    _LOGGER.debug('closing db engine ...')

    app['db_engine'].close()
    await app['db_engine'].wait_closed()
    
    _LOGGER.debug('db engine closed')


def setup_db(app):
    # appends def fun(app) -> coroutines
    app.on_startup.append(create_aiopg)
    app.on_cleanup.append(dispose_aiopg)
