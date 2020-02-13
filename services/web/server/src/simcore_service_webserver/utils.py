"""
    General utilities and helper functions
"""
import hashlib
import string
import sys
from datetime import datetime
from pathlib import Path
from secrets import choice
from typing import Iterable, List

from yarl import URL

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def is_osparc_repo_dir(path: Path) -> bool:
    return all( any(path.glob(expression)) for expression in [
        ".github",
        "packages",
        "services"] )


def search_osparc_repo_dir(max_iter=8):
    """ Returns path to root repo dir or None

        NOTE: assumes this file within repo, i.e. only happens in edit mode!
    """
    root_dir = current_dir
    if "services/web/server" in str(root_dir):
        it = 1
        while not is_osparc_repo_dir(root_dir) and it<max_iter:
            root_dir = root_dir.parent
            it += 1

        if is_osparc_repo_dir(root_dir):
            return root_dir
    return None


def as_list(obj) -> List:
    if isinstance(obj, Iterable):
        return list(obj)
    return [obj,]


def gravatar_hash(email: str) -> str:
    return hashlib.md5(email.lower().encode('utf-8')).hexdigest() # nosec


def gravatar_url(gravatarhash, size=100, default='identicon', rating='g') -> URL:
    url = URL(f'https://secure.gravatar.com/avatar/{gravatarhash}')
    return url.with_query(s=size, d=default, r=rating)


def generate_password(length: int=8, more_secure: bool=False) -> str:
    """ generate random passord

    :param length: password length, defaults to 8
    :type length: int, optional
    :param more_secure: if True it adds at least one lowercase, one uppercase and three digits, defaults to False
    :type more_secure: bool, optional
    :return: password
    :rtype: str
    """
    # Adapted from https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    alphabet = string.ascii_letters + string.digits

    if more_secure:
        # At least one lowercase, one uppercase and three digits
        while True:
            password = ''.join(choice(alphabet) for i in range(length))
            if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3):
                break
    else:
        password = ''.join(choice(alphabet) for i in range(length))

    return password


def generate_passphrase(number_of_words=4):
    # Adapted from https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    words = load_words()
    passphrase = ' '.join(choice(words) for i in range(number_of_words))
    return passphrase


def load_words():
    """
        ONLY in linux systems

    :return: a list of words
    :rtype: list of str
    """
    # FIXME: alpine does not have this file. Get from https://users.cs.duke.edu/~ola/ap/linuxwords in container
    if 'linux' not in sys.platform:
        raise OSError("load_words can only run on Linux systems.")
    with open('/usr/share/dict/words') as f:
        words = [word.strip() for word in f]
    return words



DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

def now() -> datetime:
    return datetime.utcnow()


def format_datetime(snapshot: datetime) -> str:
    #return snapshot.strftime(DATETIME_FORMAT)
    # TODO: this fullfills datetime schema!!!
    # 'pattern': '\\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\\d)T(2[0-3]|1\\d|0?[1-9])(:(\\d|[0-5]\\d)){2}(\\.\\d{3})?Z',

    # FIXME: ensure snapshot is ZULU time!
    return "{}Z".format(snapshot.isoformat(timespec='milliseconds'))


def now_str() -> str:
    """ Returns formatted time snapshot in UTC
    """
    return format_datetime(now())

def to_datetime(snapshot: str) -> datetime:
    #
    return datetime.strptime(snapshot, DATETIME_FORMAT)
