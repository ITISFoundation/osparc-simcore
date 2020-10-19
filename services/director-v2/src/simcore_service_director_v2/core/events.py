from typing import Callable

from fastapi import FastAPI

from ..meta import __version__, project_name

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


def create_start_app_handler(_app: FastAPI) -> Callable:
    def on_startup() -> None:
        print(WELCOME_MSG)

    return on_startup


def create_stop_app_handler(_app: FastAPI) -> Callable:
    def on_shutdown() -> None:
        msg = project_name + f" v{__version__} SHUT DOWN"
        print(f"{msg:=^100}")

    return on_shutdown
