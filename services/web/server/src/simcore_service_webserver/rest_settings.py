""" Configuration of rest-api subpackage

    Parameters and helper functions used to setup this subpackage
"""
from servicelib import openapi




# helpers ---

def get_base_path(specs: openapi.Spec) ->str :
    # TODO: guarantee this convention is true
    return '/v' + specs.info.version.split('.')[0]
