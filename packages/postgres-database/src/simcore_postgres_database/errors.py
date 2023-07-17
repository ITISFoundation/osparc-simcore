""" aiopg errors

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
"""
# NOTE: psycopg2.errors are created dynamically
# pylint: disable=no-name-in-module
from psycopg2 import DatabaseError, DataError
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
    NotNullViolation,
    UniqueViolation,
)

assert issubclass(UniqueViolation, IntegrityError)  # nosec

# TODO: see https://stackoverflow.com/questions/58740043/how-do-i-catch-a-psycopg2-errors-uniqueviolation-error-in-a-python-flask-app
# from sqlalchemy.exc import IntegrityError
#
# from psycopg2.errors import UniqueViolation
#
#    try:
#        s.commit()
#   except IntegrityError as e:
#        assert isinstance(e.orig, UniqueViolation)


__all__: tuple[str, ...] = (
    "CheckViolation",
    "DatabaseError",
    "DataError",
    "DBAPIError",
    "ForeignKeyViolation",
    "IntegrityError",
    "InterfaceError",
    "InternalError",
    "NotNullViolation",
    "NotSupportedError",
    "OperationalError",
    "ProgrammingError",
    "UniqueViolation",
)
# nopycln: file
