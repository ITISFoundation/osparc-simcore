"""
 TODO: this is a placeholder for the command line interface module
"""
import argparse

from . import settings

def add_options(ap=None):
    """ Creates an arguments parser and adds options to it

    Returns instance of the argparse.ArgumentParser
    """
    # TODO: single setup per application? or use click?
    if ap is None:
        ap = argparse.ArgumentParser()

    # TODO: any module could add extra options. See click!
    ap = settings.add_cli_options(ap)

    # TODO: Add here more options?

    return ap

def parse_options(argv, ap=None):
    # ignore unknown options
    options, _ = ap.parse_known_args(argv)

    return options
