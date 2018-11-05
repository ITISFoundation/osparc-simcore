#/bin/bash
docker build ../../../scripts/openapi/oas_resolver -t oas_resolver
docker run -v $PWD/../src/simcore_service_storage/oas3/v0:/input \
            -v $PWD:/output \
            oas_resolver /input/openapi.yaml /output/output.yaml

../../../scripts/openapi/openapi_codegen.sh \
    -i output.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json

rm -f output.yaml