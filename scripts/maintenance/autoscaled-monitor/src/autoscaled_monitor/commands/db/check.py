"""``db check`` — verify database connectivity."""

import asyncio

from ... import db
from ..._state import state


def check() -> None:
    """Check the connection to the simcore database."""
    asyncio.run(db.check_db_connection(state))
