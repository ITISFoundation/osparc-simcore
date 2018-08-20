"""
 TODO: this is a placeholder for the command line interface module
"""
import argparse

from . import settings

def setup():
    """
        TODO: any module could add extra options. See click!
    """
    ap = argparse.ArgumentParser()
    ap = settings.add_cli_options(ap)

    # TODO: Add here more options?

    return ap

def parse_options(argv, ap):
    # ignore unknown options
    options, _ = ap.parse_known_args(argv)

    return options
