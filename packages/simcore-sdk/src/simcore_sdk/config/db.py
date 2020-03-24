""" Basic configuration file for postgres service

"""
from os import environ as env

import trafaret as T

CONFIG_SCHEMA = T.Dict({
    "database": T.String(),
    "user": T.String(),
    "password": T.String(),
    T.Key("minsize", default=1 ,optional=True): T.Int(),
    T.Key("maxsize", default=4, optional=True): T.Int(),
    "host": T.Or( T.String, T.Null),
    "port": T.Or( T.Int, T.Null),
    "endpoint": T.Or( T.String, T.Null)
})


# TODO: deprecate!
class Config():

    def __init__(self):
        # TODO: uniform config classes . see server.config file
        POSTGRES_URL = env.get("POSTGRES_ENDPOINT", "postgres:5432")
        POSTGRES_USER = env.get("POSTGRES_USER", "simcore")
        POSTGRES_PW = env.get("POSTGRES_PASSWORD", "simcore")
        POSTGRES_DB = env.get("POSTGRES_DB", "simcoredb")

        self._user = POSTGRES_USER
        self._pwd = POSTGRES_PW
        self._url = POSTGRES_URL
        self._db = POSTGRES_DB
        self._endpoint = 'postgresql+psycopg2://{user}:{pw}@{url}/{db}'.format(
            user=self._user, pw=self._pwd, url=self._url, db=self._db)

    @property
    def endpoint(self):
        return self._endpoint
