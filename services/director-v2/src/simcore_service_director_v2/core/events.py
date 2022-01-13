from servicelib.async_utils import stop_sequential_workers

from ..meta import PROJECT_NAME, __version__

#
# SEE https://patorjk.com/software/taag/#p=display&f=Small&t=Director
#
WELCOME_MSG = r"""
______ _               _
|  _  (_)             | |
| | | |_ _ __ ___  ___| |_ ___  _ __
| | | | | '__/ _ \/ __| __/ _ \| '__|
| |/ /| | | |  __/ (__| || (_) | |
|___/ |_|_|  \___|\___|\__\___/|_|   {0}

""".format(
    f"v{__version__}"
)


async def on_startup() -> None:
    print(WELCOME_MSG, flush=True)


async def on_shutdown() -> None:
    await stop_sequential_workers()
    msg = PROJECT_NAME + f" v{__version__} SHUT DOWN"
    print(f"{msg:=^100}", flush=True)
