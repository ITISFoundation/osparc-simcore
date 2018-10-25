"""

TODO: test!

SEE https://aiopg.readthedocs.io/en/stable/
SEE asyncpg https://magicstack.github.io/asyncpg/current/index.html
"""
import aiopg.sa
import attr
import psycopg2
import sqlalchemy as sa
import logging
import warnings

log = logging.getLogger(__name__)

warnings.warn("DO NOT USER, STILL UNDER DEVELOPMENT")

@attr.s(auto_attribs=True)
class AiopgExecutor:
    """
        Executes sa statements using aiopg Engine

    SEE https://github.com/aio-libs/aiopg/issues/321
    SEE http://docs.sqlalchemy.org/en/latest/faq/metadata_schema.html#how-can-i-get-the-create-table-drop-table-output-as-a-string)
    """
    engine: aiopg.sa.engine.Engine
    statement: str=None
    dsn: str=None # Data Source Name

    @property
    def sa_engine(self):
        return sa.create_engine(
            self.dsn,
            strategy="mock",
            executor=self._compile
        )

    def _compile(self, sql, *multiparams, **params):
        # pylint: disable=W0613, unused-argument
        self.statement = str(sql.compile(dialect=self.sa_engine.dialect))

    async def execute(self):
        async with self.engine.acquire() as conn:
            log.debug(self.statement)
            import pdb; pdb.set_trace()

            resp = await conn.execute(self.statement)
            return resp




async def create_all(engine: aiopg.sa.engine.Engine, metadata: sa.MetaData, dsn: str):
    executor = AiopgExecutor(engine, dsn=dsn)
    metadata.create_all(executor.sa_engine, checkfirst=True)
    await executor.execute()


async def drop_all(engine: aiopg.sa.engine.Engine, metadata: sa.MetaData):
    executor = AiopgExecutor(engine)
    metadata.drop_all(executor.sa_engine, checkfirst=True)
    await executor.execute()


# EXCEPTIONS -------------------------------------
#
# aiopg reuses DBAPI exceptions
#
# StandardError
# |__ Warning
# |__ Error
#     |__ InterfaceError
#     |__ DatabaseError
#         |__ DataError
#         |__ OperationalError
#         |__ IntegrityError
#         |__ InternalError
#         |__ ProgrammingError
#         |__ NotSupportedError
#
# SEE https://aiopg.readthedocs.io/en/stable/core.html?highlight=Exception#exceptions
# SEE http://initd.org/psycopg/docs/module.html#dbapi-exceptions

# alias add prefix DBAPI
DBAPIError = psycopg2.Error


__all__ = (
    'create_all',
    'drop_all'
)
