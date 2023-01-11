from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_base import (
    ReservedContextKeys,
)


def test_reserved_context_keys():
    user_defined_keys: set[str] = set()
    for key_name, value in ReservedContextKeys.__dict__.items():
        if isinstance(value, str) and not key_name.startswith("_"):
            user_defined_keys.add(value)

    assert (
        user_defined_keys == ReservedContextKeys.RESERVED
    ), "please make sure all keys starting with `_` are also listed inside RESERVED"
