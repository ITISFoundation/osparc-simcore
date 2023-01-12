from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_base import (
    ReservedContextKeys,
)


def test_asd():
    assert ReservedContextKeys.is_reserved("app") is True
    assert ReservedContextKeys.is_reserved("missing") is False
    assert ReservedContextKeys.is_stored_locally("app") is True
    assert ReservedContextKeys.is_reserved("missing") is False
