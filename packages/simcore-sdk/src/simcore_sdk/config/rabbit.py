""" Basic configuration file for rabbitMQ

"""

from os import environ as env

import pika
import yaml
import trafaret as T


# TODO: adapt all data below!
# TODO: can use venv as defaults? e.g. $RABBIT_LOG_CHANNEL
CONFIG_SCHEMA = T.Dict({
    T.Key("name", default="tasks", optional=True): T.String(),
    T.Key("enabled", default=True, optional=True): T.Bool(),
    T.Key("host", default='rabbit', optional=True): T.String(),
    T.Key("port", default=5672, optional=True): T.Int(),
    "user": T.String(),
    "password": T.String(),
    "channels": T.Dict({
        "progress": T.String(),
        "log": T.String(),
    T.Key("celery", default=dict(result_backend="rpc://"), optional=True): T.Dict({
        T.Key("result_backend", default="${CELERY_RESULT_BACKEND}", optional=True): T.String()
        })
    })
})


CONFIG_EXAMPLES = map(yaml.safe_load,[
"""
  user: simcore
  password: simcore
  channels:
    log: comp.backend.channels.log
    progress: comp.backend.channels.progress
""",
"""
  host: rabbito
  port: 1234
  user: foo
  password: secret
  channels:
    log: comp.backend.channels.log
    progress: comp.backend.channels.progress
""",
"""
  user: bar
  password: secret
  channels:
    log: comp.backend.channels.log
    progress: comp.backend.channels.progress
  celery:
    result_backend: 'rpc://'
"""])


def eval_broker(config):
    """
        Raises trafaret.DataError if config validation fails
    """
    CONFIG_SCHEMA.check(config) # raise exception
    url = 'amqp://{user}:{password}@{host}:{port}'.format(**config)
    return url


# TODO: deprecate! -----------------------------------------------------------------------------
# TODO: uniform config classes . see server.config file

class Config:
    def __init__(self, config=None):
        if config is not None:
            CONFIG_SCHEMA.check(config) # raise exception
        else:
            config = {}

        RABBIT_USER = env.get('RABBIT_USER','simcore')
        RABBIT_PASSWORD = env.get('RABBIT_PASSWORD','simcore')
        RABBIT_HOST=env.get('RABBIT_HOST','rabbit')
        RABBIT_PORT=int(env.get('RABBIT_PORT', 5672))
        RABBIT_LOG_CHANNEL = env.get('RABBIT_LOG_CHANNEL','comp.backend.channels.log')
        RABBIT_PROGRESS_CHANNEL = env.get('RABBIT_PROGRESS_CHANNEL','comp.backend.channels.progress')
        CELERY_RESULT_BACKEND=env.get('CELERY_RESULT_BACKEND','rpc://')
        # FIXME: get variables via config.get('') or
        # rabbit

        try:
            self._broker_url = eval_broker(config)
        except:                                     # pylint: disable=W0702
            self._broker_url = 'amqp://{user}:{pw}@{url}:{port}'.format(user=RABBIT_USER, pw=RABBIT_PASSWORD, url=RABBIT_HOST, port=RABBIT_PORT)

        self._result_backend = config.get("celery", {}).get("result_backend") or CELERY_RESULT_BACKEND
        self._module_name = config.get("name") or "tasks"

        # pika
        self._pika_credentials = pika.PlainCredentials(
                config.get("user") or RABBIT_USER,
                config.get("password") or RABBIT_PASSWORD)
        self._pika_parameters = pika.ConnectionParameters(
            host=config.get("host") or RABBIT_HOST,
            port=config.get("port") or RABBIT_PORT,
            credentials=self._pika_credentials,
            connection_attempts=100)

        self._log_channel = config.get("celery", {}).get("result_backend") or RABBIT_LOG_CHANNEL
        self._progress_channel = config.get("celery", {}).get("result_backend") or RABBIT_PROGRESS_CHANNEL

    @property
    def parameters(self):
        return self._pika_parameters

    @property
    def log_channel(self):
        return self._log_channel

    @property
    def progress_channel(self):
        return self._progress_channel

    @property
    def broker(self):
        return self._broker_url

    @property
    def backend(self):
        return self._result_backend

    @property
    def name(self):
        return self._module_name
