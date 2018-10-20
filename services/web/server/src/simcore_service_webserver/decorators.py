
from functools import wraps

from aiohttp_security.api import has_permission, login_required


def args_adapter(func):
    """
        Patch to fix bug1 in issue #186 between aiohttp_security

        request = args[-1]

        and swaggerRouter
    """
    @wraps(func)
    def wrapped(*args, **kargs):
        new_args = list(args)
        new_kargs = kargs.copy()

        if 'request' in kargs:
            new_args.append(kargs['request'])
            new_kargs.pop('request')
        return func(*new_args, **new_kargs)

    return wrapped


__all__ = (
    'args_adapter',
    'login_required', 'has_permission' # decorators
)
