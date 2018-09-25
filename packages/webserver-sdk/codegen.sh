#/bin/bash
exec ../../scripts/openapi/openapi_codegen.sh \
    -i ../../services/web/server/src/simcore_service_webserver/oas3/v1/openapi.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json
