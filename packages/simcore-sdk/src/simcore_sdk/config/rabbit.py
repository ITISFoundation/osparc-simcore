""" Basic configuration file for rabbitMQ

"""

from os import environ as env

import pika
import yaml
import trafaret as T


# TODO: adapt all data below!
# TODO: can use venv as defaults? e.g. $RABBITMQ_LOG_CHANNEL
CONFIG_SCHEMA = T.Dict({
    T.Key("host", default='rabbit', optional=True): T.String(),
    T.Key("port", default=5672, optional=True): T.Int(),
    "user": T.String(),
    "password": T.String(),
    "channels": T.Dict({
        "progress": T.String(),
        "log": T.String(),
    })
})

CONFIG_EXAMPLES = map(yaml.load,[
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
""",])


def eval_broker(config):
    """
        Raises trafaret.DataError if config validation fails
    """
    CONFIG_SCHEMA.check(config) # raise exception
    url = 'amqp://{user}:{password}@{host}:{port}'.format(**config)
    return url



# TODO: deprecate!
# TODO: uniform config classes . see server.config file
RABBITMQ_USER = env.get('RABBITMQ_USER','simcore')
RABBITMQ_PASSWORD = env.get('RABBITMQ_PASSWORD','simcore')
RABBITMQ_HOST="rabbit"
RABBITMQ_PORT=5672
RABBITMQ_LOG_CHANNEL = env.get('RABBITMQ_LOG_CHANNEL','comp.backend.channels.log')
RABBITMQ_PROGRESS_CHANNEL = env.get('RABBITMQ_PROGRESS_CHANNEL','comp.backend.channels.progress')

AMQ_URL = 'amqp://{user}:{pw}@{url}:{port}'.format(user=RABBITMQ_USER, pw=RABBITMQ_PASSWORD, url=RABBITMQ_HOST, port=RABBITMQ_PORT)

CELERY_BROKER_URL = AMQ_URL
CELERY_RESULT_BACKEND=env.get('CELERY_RESULT_BACKEND','rpc://')

class Config():
    def __init__(self):
        # rabbit
        self._broker_url = CELERY_BROKER_URL
        self._result_backend = CELERY_RESULT_BACKEND
        self._module_name = "tasks"

        # pika
        self._pika_credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        self._pika_parameters = pika.ConnectionParameters(host=RABBITMQ_HOST,
            port=RABBITMQ_PORT, credentials=self._pika_credentials, connection_attempts=100)

        self._log_channel = RABBITMQ_LOG_CHANNEL
        self._progress_channel = RABBITMQ_PROGRESS_CHANNEL

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
