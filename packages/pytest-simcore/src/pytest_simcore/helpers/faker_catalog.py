from simcore_service_api_server.services_http.catalog import TruncatedCatalogServiceOut


def create_service_out(**overrides):
    # FIXME: should change when schema changes

    obj = {
        "name": "Fast Counter",
        "description": "Counts fast",
        "key": "simcore/service/dynanic/itis/sim4life"
        if overrides.get("type") == "dynamic"
        else "simcore/services/comp/itis/sleeper",
        "version": "1.0.0",
        "integration-version": "1.0.0",
        "type": "computational",
        "authors": [
            {
                "name": "Jim Knopf",
                "email": "sun@sense.eight",
                "affiliation": "Sense8",
            }
        ],
        "contact": "lab@net.flix",
        "inputs": {},
        "outputs": {},
        "owner": "user@example.com",
    }
    obj.update(**overrides)

    assert TruncatedCatalogServiceOut.model_validate(obj)
    return obj
