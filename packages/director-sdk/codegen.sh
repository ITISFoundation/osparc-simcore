#/bin/bash
exec ../../scripts/openapi/openapi_codegen.sh \
    -i ../../services/director/src/simcore_service_director/.openapi/v1/director_api.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json