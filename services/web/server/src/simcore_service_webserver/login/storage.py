from logging import getLogger
from datetime import datetime
import enum
import asyncpg

from .utils import get_random_string
from . import sql

from ..db_models import UserRole, UserStatus, ConfirmationAction


log = getLogger(__name__)

class AsyncpgStorage:
    def __init__(self, pool, *,
                 user_table_name='users',
                 confirmation_table_name='confirmations'):
        self.pool = pool
        self.user_tbl = user_table_name
        self.confirm_tbl = confirmation_table_name

    async def get_user(self, with_data) -> asyncpg.Record:
        # FIXME: these can throw!!!!
        async with self.pool.acquire() as conn:
            data =  await sql.find_one(conn, self.user_tbl, with_data)
            return data

    async def create_user(self, data) -> asyncpg.Record:
        data.setdefault('created_at', datetime.utcnow())
        async with self.pool.acquire() as conn:
            data['id'] = await sql.insert(conn, self.user_tbl, data)
        return data

    async def update_user(self, user, updates) -> asyncpg.Record:
        async with self.pool.acquire() as conn:
            await sql.update(conn, self.user_tbl, {'id': user['id']}, updates)

    async def delete_user(self, user):
        async with self.pool.acquire() as conn:
            await sql.delete(conn, self.user_tbl, {'id': user['id']})

    async def create_confirmation(self, user, action, data=None) -> asyncpg.Record:
        async with self.pool.acquire() as conn:
            while True:
                code = get_random_string(30)
                if not await sql.find_one(conn, self.confirm_tbl,
                                          {'code': code}):
                    break
            confirmation = {
                'code': code,
                'user_id': user['id'],
                'action': action,
                'data': data,
                'created_at': datetime.utcnow(),
            }
            await sql.insert(conn, self.confirm_tbl, confirmation, None)
            return confirmation

    async def get_confirmation(self, filter_dict) -> asyncpg.Record:
        if 'user' in filter_dict:
            filter_dict['user_id'] = filter_dict.pop('user')['id']
        async with self.pool.acquire() as conn:
            confirmation = await sql.find_one(conn, self.confirm_tbl, filter_dict)
            return confirmation

    async def delete_confirmation(self, confirmation):
        async with self.pool.acquire() as conn:
            await sql.delete(conn, self.confirm_tbl,
                             {'code': confirmation['code']})





# helpers ----------------------------
def _to_enum(data):
    # FIXME: cannot modify asyncpg.Record:

    # TODO: ensure columns names and types! User tables for that
    # See https://docs.sqlalchemy.org/en/latest/core/metadata.html
    if data:
        for key, enumtype in ( ('status', UserStatus),
                            ('role', UserRole),
                            ('action', ConfirmationAction) ):
            if key in data:
                data[key] = getattr(enumtype, data[key])
    return data

def _to_name(data):
    if data:
        for key in ('status', 'role', 'action'):
            if key in data:
                if isinstance(data[key], enum.Enum):
                    data[key] = data[key].name
    return data
