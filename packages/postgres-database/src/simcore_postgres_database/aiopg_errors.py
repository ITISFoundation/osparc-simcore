"""aiopg errors

WARNING: these errors are not raised by asyncpg. Therefore all code using new sqlalchemy.ext.asyncio
         MUST use instead import sqlalchemy.exc exceptions!!!!

StandardError
|__ Warning
|__ Error
    |__ InterfaceError
    |__ DatabaseError
        |__ DataError
        |__ OperationalError
        |__ IntegrityError
        |__ InternalError
        |__ ProgrammingError
        |__ NotSupportedError

- aiopg reuses DBAPI exceptions
    SEE https://aiopg.readthedocs.io/en/stable/core.html?highlight=Exception#exceptions
    SEE http://initd.org/psycopg/docs/module.html#dbapi-exceptions
    SEE https://www.postgresql.org/docs/current/errcodes-appendix.html
"""

# NOTE: psycopg2.errors are created dynamically
# pylint: disable=no-name-in-module
from psycopg2 import (
    DatabaseError,
    DataError,
)
from psycopg2 import Error as DBAPIError
from psycopg2 import (
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
)
from psycopg2.errors import (
    CheckViolation,
    ForeignKeyViolation,
    InvalidTextRepresentation,
    NotNullViolation,
    UniqueViolation,
)

assert issubclass(UniqueViolation, IntegrityError)  # nosec

__all__: tuple[str, ...] = (
    "CheckViolation",
    "DBAPIError",
    "DataError",
    "DatabaseError",
    "ForeignKeyViolation",
    "IntegrityError",
    "InterfaceError",
    "InternalError",
    "InvalidTextRepresentation",
    "NotNullViolation",
    "NotSupportedError",
    "OperationalError",
    "ProgrammingError",
    "UniqueViolation",
)
# nopycln: file
