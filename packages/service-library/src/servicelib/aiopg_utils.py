""" Helpers for aiopg

    - aiopg is used as client sdk to interact with postgres database asynchronously

"""

from psycopg2 import Error as DBAPIError

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



__all__ = [
    'DBAPIError'
]
