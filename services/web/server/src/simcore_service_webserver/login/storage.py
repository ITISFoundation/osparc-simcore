from logging import getLogger
from datetime import datetime

from .utils import get_random_string
from . import sql


log = getLogger(__name__)


class AsyncpgStorage:
    def __init__(self, pool, *,
                 user_table_name='users',
                 confirmation_table_name='confirmations'):
        self.pool = pool
        self.user_tbl = user_table_name
        self.confirm_tbl = confirmation_table_name

    async def get_user(self, filter_dict):
        # FIXME: these can throw!!!!
        async with self.pool.acquire() as conn:
            return await sql.find_one(conn, self.user_tbl, filter_dict)

    async def create_user(self, data):
        data.setdefault('created_at', datetime.utcnow())
        async with self.pool.acquire() as conn:
            data['id'] = await sql.insert(conn, self.user_tbl, data)
        return data

    async def update_user(self, user, updates):
        async with self.pool.acquire() as conn:
            await sql.update(conn, self.user_tbl, {'id': user['id']}, updates)

    async def delete_user(self, user):
        async with self.pool.acquire() as conn:
            await sql.delete(conn, self.user_tbl, {'id': user['id']})

    async def create_confirmation(self, user, action, data=None):
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

    async def get_confirmation(self, filter_dict):
        if 'user' in filter_dict:
            filter_dict['user_id'] = filter_dict.pop('user')['id']
        async with self.pool.acquire() as conn:
            return await sql.find_one(conn, self.confirm_tbl, filter_dict)

    async def delete_confirmation(self, confirmation):
        async with self.pool.acquire() as conn:
            await sql.delete(conn, self.confirm_tbl,
                             {'code': confirmation['code']})

    def user_id_from_string(self, id_str):
        try:
            return int(id_str)
        except ValueError as ex:
            log.error('Can\'t convert string into id', exc_info=ex)

    def user_session_id(self, user):
        return str(user['id'])
