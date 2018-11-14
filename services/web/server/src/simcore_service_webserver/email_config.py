""" email's subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T


CONFIG_SECTION_NAME = 'smtp'


schema = T.Dict({
    T.Key('sender', default='OSPARC support <crespo@itis.swiss>'): T.String(), # FIXME: email format
    'host': T.String(),
    'port': T.Int(),
    T.Key('tls', default=False): T.Bool(),
    T.Key('username', default=None): T.Or(T.String, T.Null),
    T.Key('password', default=None): T.Or(T.String, T.Null)
    }
)
