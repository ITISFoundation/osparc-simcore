# pylint: disable-all
#
# Support for pydantic model's dict
# Ensures items in resulting dict are "json friendly"
#
# SEE https://fastapi.tiangolo.com/tutorial/encoder/
#

try:
    from fastapi.encoders import jsonable_encoder

except ImportError:  # for aiohttp-only services
    # Taken 'as is' from https://github.com/tiangolo/fastapi/blob/master/fastapi/encoders.py
    # to be used in aiohttp-based services w/o having to install fastapi
    #
    # NOTE: that this might be at some point part of pydantic
    # https://github.com/samuelcolvin/pydantic/issues/951#issuecomment-552463606
    #
    from ._original_fastapi_encoders import jsonable_encoder

    servicelib_jsonable_encoder = jsonable_encoder  # alias

__all__ = ("jsonable_encoder",)
