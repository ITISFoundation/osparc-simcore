REQUIRED = object()
DEFAULTS = {
    'COMMON_THEME': 'templates/common',
    'PASSWORD_LEN': (6, 30),
    'LOGIN_REDIRECT': '/',
    'LOGOUT_REDIRECT': '/',
    'REGISTRATION_CONFIRMATION_REQUIRED': False, # TODO: activate when

    # TODO: add in configuration file as environ!
    'SMTP_SENDER': None,
    'SMTP_HOST': REQUIRED,
    'SMTP_PORT': REQUIRED,
    'SMTP_TLS': False,
    'SMTP_USERNAME': None,
    'SMTP_PASSWORD': None,

    # email confirmation links lifetime in days
    'REGISTRATION_CONFIRMATION_LIFETIME': 5,
    'RESET_PASSWORD_CONFIRMATION_LIFETIME': 5,
    'CHANGE_EMAIL_CONFIRMATION_LIFETIME': 5,

    'MSG_LOGGED_IN': 'You are logged in',
    'MSG_LOGGED_OUT': 'You are logged out',
    'MSG_ACTIVATED': 'Your account is activated',
    'MSG_UNKNOWN_EMAIL': 'This email is not registered',
    'MSG_WRONG_PASSWORD': 'Wrong password',
    'MSG_USER_BANNED': 'This user is banned',
    'MSG_ACTIVATION_REQUIRED': ('You have to activate your account via'
                                ' email, before you can login'),
    'MSG_EMAIL_EXISTS': 'This email is already registered',
    'MSG_OFTEN_RESET_PASSWORD': (
        'You can not request of restoring your password so often. Please, use'
        ' the link we sent you recently'),
    'MSG_CANT_SEND_MAIL': 'Can\'t send email, try a little later',
    'MSG_PASSWORDS_NOT_MATCH': 'Passwords must match',
    'MSG_PASSWORD_CHANGED': 'Your password is changed',
    'MSG_CHANGE_EMAIL_REQUESTED': ('Please, click on the verification link'
                                   ' we sent to your new email address'),
    'MSG_EMAIL_CHANGED': 'Your email is changed',
    'MSG_AUTH_FAILED': 'Authorization failed',

    # next settings are initialized during `setup()`, do not set it manually
    'APP': REQUIRED,
    'STORAGE': REQUIRED,
}


# pylint: disable=W0231
class Cfg(dict):
    '''
    Settings storage witch suports both, dict and dot notations

    >>> cfg = Cfg({'foo': 1, 'bar': 2, 'baz': REQUIRED})

    >>> cfg.attr
    Traceback (most recent call last):
        ...
    RuntimeError: Settings are not configured yet

    >>> cfg['item']
    Traceback (most recent call last):
        ...
    RuntimeError: Settings are not configured yet

    >>> cfg.configure({})
    Traceback (most recent call last):
        ...
    RuntimeError: You have to set `baz`

    >>> cfg.configure({'bar': 3, 'baz': 4})
    >>> cfg['foo']
    1
    >>> cfg['bar']
    3
    >>> cfg['baz']
    4
    >>> cfg.foo
    1
    >>> cfg.bar
    3
    >>> cfg.baz
    4

    >>> cfg['unknown']
    Traceback (most recent call last):
        ...
    KeyError: 'unknown'

    >>> cfg.unknown
    Traceback (most recent call last):
        ...
    AttributeError
    '''

    def __init__(self, defaults):
        self.defaults = defaults
        self.configured = False

    # pylint: disable=E0202
    def __getitem__(self, name):
        if not self.configured:
            raise RuntimeError('Settings are not configured yet')
        self.__getitem__ = super().__getitem__
        return super().__getitem__(name)

    def __getattr__(self, name):
        if name == '__wrapped__':
            raise AttributeError
        try:
            return self[name]
        except KeyError:
            raise AttributeError

    def configure(self, updates):
        self.clear()
        for key in self.defaults:
            value = updates.get(key, self.defaults[key])
            if value == REQUIRED:
                raise RuntimeError('You have to set `{}`'.format(key))
            self[key] = value
        self.configured = True


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
else:
    cfg = Cfg(DEFAULTS)
