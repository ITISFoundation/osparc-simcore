#/bin/bash
exec ../../scripts/openapi/openapi_codegen.sh \
    -i ../../services/director/src/simcore_service_director/.oas3/v1/openapi.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json