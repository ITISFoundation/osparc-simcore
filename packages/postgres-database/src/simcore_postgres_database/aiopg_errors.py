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

import warnings

# NOTE: psycopg2.errors are created dynamically
# pylint: disable=no-name-in-module
from psycopg2 import (
    DatabaseError,
    DataError,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
)
from psycopg2 import Error as DBAPIError
from psycopg2.errors import (
    CheckViolation,
    ForeignKeyViolation,
    InvalidTextRepresentation,
    NotNullViolation,
    UniqueViolation,
)

assert issubclass(UniqueViolation, IntegrityError)  # nosec


warnings.warn(
    (
        "DEPRECATED: The aiopg DBAPI exceptions in this module are no longer used. "
        "Please use exceptions from the `sqlalchemy.exc` module instead. "
        "See https://docs.sqlalchemy.org/en/21/core/exceptions.html for details. "
        "This change is part of the migration to SQLAlchemy async support with asyncpg. "
        "See migration issue: https://github.com/ITISFoundation/osparc-simcore/issues/4529"
    ),
    DeprecationWarning,
    stacklevel=2,
)

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
