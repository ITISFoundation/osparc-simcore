""" Basic configuration file for postgres

"""
from os import environ as env



class Config():
    def __init__(self):
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