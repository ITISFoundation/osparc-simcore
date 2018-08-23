#!/bin/bash
input=./src/director/.openapi/v1/director_api.yaml
outputdir=./src/director/generated_code
absinputpath=$(realpath "${input}")
absoutputdir=$(realpath "${outputdir}")
../../scripts/openapi_python_server_codegen.sh -i ${absinputpath} -o ${absoutputdir}