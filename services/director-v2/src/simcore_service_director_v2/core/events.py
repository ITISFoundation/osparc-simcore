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


def on_startup() -> None:
    print(WELCOME_MSG)


def on_shutdown() -> None:
    msg = project_name + f" v{__version__} SHUT DOWN"
    print(f"{msg:=^100}")
