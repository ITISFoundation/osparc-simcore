import functools
import logging


from sqlalchemy import (
    create_engine
)


log = logging.getLogger(__name__)

DNS = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


@functools.lru_cache(maxsize=10, typed=True)
def acquire_engine(url):
    log.debug("Creating engine to %s ...", url)
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    return engine


def acquire_admin_engine(**options):
    admin_db_url = DNS.format(
        user="postgres",
        password="postgres",
        database="postgres",
        host=options["host"],
        port=options["port"],
    )
    # TODO: what is isolation_level?
    engine = acquire_engine(admin_db_url)
    return engine
