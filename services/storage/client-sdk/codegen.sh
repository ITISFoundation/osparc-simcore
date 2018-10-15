#/bin/bash
# TODO: unify scripts
exec ../../../scripts/openapi/openapi_codegen.sh \
    -i ../src/simcore_service_storage/oas3/v0/openapi.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json
