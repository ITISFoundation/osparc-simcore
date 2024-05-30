# pylint: disable=unused-argument

from fastapi import FastAPI


def setup(app: FastAPI, *, is_debug: bool = False):
    ...
