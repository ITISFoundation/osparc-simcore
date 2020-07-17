#! /bin/bash

../../../scripts/openapi/openapi_codegen.sh \
  -i ../src/simcore_service_storage/api/v0/openapi.yaml \
  -o . \
  -g python \
  -c ./codegen_config.json

# rm -f output.yaml
