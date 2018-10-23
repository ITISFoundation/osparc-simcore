from yarl import URL

from simcore_service_webserver.db_models import UserStatus, UserRole
from simcore_service_webserver.login.cfg import cfg
from simcore_service_webserver.login.utils import (encrypt_password,
                                                   get_random_string)


class NewUser:
    def __init__(self, params=None):
        self.params = params
        self.user = None

    async def __aenter__(self):
        self.user = await create_user(self.params)
        return self.user

    async def __aexit__(self, *args):
        await cfg.STORAGE.delete_user(self.user)


async def create_user(data=None):
    data = data or {}
    password = get_random_string(10)
    params = {
        'name': get_random_string(10),
        'email': '{}@gmail.com'.format(get_random_string(10)),
        'password_hash': encrypt_password(password)
    }
    params.update(data)
    params.setdefault('status', UserStatus.ACTIVE.name)
    params.setdefault('role', UserRole.USER.name)
    params.setdefault('created_ip', '127.0.0.1')
    user = await cfg.STORAGE.create_user(params)
    user['raw_password'] = password
    return user


def unwrap_envelope(payload):
    return tuple(payload.get(k) for k in ('data', 'error'))

def parse_link(text):
    link = text.split('<a href="')[1].split('"')[0]
    assert '/auth/confirmation/' in link
    return URL(link).path
