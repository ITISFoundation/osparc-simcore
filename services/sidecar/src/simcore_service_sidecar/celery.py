import logging

from celery.signals import worker_ready, worker_shutting_down

from .__version__ import __version__
from .celery_configurator import create_celery_app
from .celery_task_utils import cancel_task
from .cli import run_sidecar
from .remote_debug import setup_remote_debugging

setup_remote_debugging()

app = create_celery_app()

log = logging.getLogger(__name__)

WELCOME_MSG = r"""
  .-')            _ .-') _     ('-.               ('-.     _  .-')
 ( OO ).         ( (  OO) )  _(  OO)             ( OO ).-.( \( -O )
(_)---\_)  ,-.-') \     .'_ (,------.   .-----.  / . --. / ,------.
/    _ |   |  |OO),`'--..._) |  .---'  '  .--./  | \-.  \  |   /`. '
\  :` `.   |  |  \|  |  \  ' |  |      |  |('-..-'-'  |  | |  /  | |
 '..`''.)  |  |(_/|  |   ' |(|  '--.  /_) |OO  )\| |_.'  | |  |_.' |
.-._)   \ ,|  |_.'|  |   / : |  .--'  ||  |`-'|  |  .-.  | |  .  '.'
\       /(_|  |   |  '--'  / |  `---.(_'  '--'\  |  | |  | |  |\  \
 `-----'   `--'   `-------'  `------'   `-----'  `--' `--' `--' '--' {0}
""".format(
    __version__
)


@worker_shutting_down.connect
def worker_shutting_down_handler(
    # pylint: disable=unused-argument
    sig,
    how,
    exitcode,
    **kwargs
):
    # NOTE: this function shall be adapted when we switch to python 3.7+
    log.warning("detected worker_shutting_down signal(%s, %s, %s)", sig, how, exitcode)
    cancel_task(run_sidecar)


@worker_ready.connect
def worker_ready_handler(*args, **kwargs):  # pylint: disable=unused-argument
    print(WELCOME_MSG, flush=True)


__all__ = ["app"]
