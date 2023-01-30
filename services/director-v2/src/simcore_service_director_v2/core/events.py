from servicelib.async_utils import cancel_sequential_workers

from ..meta import __version__, info

#
# SEE https://patorjk.com/software/taag/#p=display&f=Small&t=Director
#
APP_STARTED_BANNER_MSG = r"""
______ _               _
|  _  (_)             | |
| | | |_ _ __ ___  ___| |_ ___  _ __
| | | | | '__/ _ \/ __| __/ _ \| '__|
| |/ /| | | |  __/ (__| || (_) | |
|___/ |_|_|  \___|\___|\__\___/|_|   {}

""".format(
    f"v{__version__}"
)

APP_FINISHED_BANNER_MSG = info.get_finished_banner()


async def on_startup() -> None:
    print(APP_STARTED_BANNER_MSG, flush=True)


async def on_shutdown() -> None:
    await cancel_sequential_workers()
    print(APP_FINISHED_BANNER_MSG, flush=True)
