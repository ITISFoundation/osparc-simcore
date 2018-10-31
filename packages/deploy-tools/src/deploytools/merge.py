""" Merges based on docker-compose tools
"""

from itertools import accumulate, chain
from typing import Dict, List, TypeVar

T = TypeVar('T')


def merge_lists(lhs: List[T], rhs: List[T]) -> List:
    # NOTE assumes all elements in the list are of the same type!
    # NOTE: does not respect order
    res = list( set(lhs + rhs) )
    return res


def merge_dicts(lhs: Dict, rhs: Dict) -> Dict:

    merged_keys = set( chain(lhs.keys(), rhs.keys()) )
    res = dict.fromkeys(merged_keys, None)
    for key in merged_keys:
        if key in lhs:
            lhs_value = lhs[key]
            if key not in rhs:
                res[key] = lhs_value
            else: # rhs overrides
                assert key in rhs
                rhs_value = rhs[key]
                if isinstance(rhs_value, dict):
                    res[key] = merge_dicts(lhs_value, rhs_value)
                elif isinstance(rhs_value, list):
                    res[key] = merge_lists(lhs_value, rhs_value)
                else:
                    res[key] = rhs_value
        else:
            res[key] = rhs[key]

    return res


def merge_docker_compose(*compose_dicts):
    return list(accumulate(compose_dicts, merge_dicts))[-1]
