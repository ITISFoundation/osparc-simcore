#/bin/sh
#
# TODO: Uses https://github.com/OpenAPITools tools instead of swagger-codegen.
#  THIS IS THE LAST VERSION!
#    https://github.com/OpenAPITools/openapi-generator/blob/master/docs/migration-from-swagger-codegen.md
#
# https://github.com/OpenAPITools/openapi-generator/releases/tag/v3.0.0
# https://angular.schule/blog/2018-06-swagger-codegen-is-now-openapi-generator

#docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate \
#    -i https://raw.githubusercontent.com/openapitools/openapi-generator/master/modules/openapi-generator/src/test/resources/2_0/petstore.yaml \
#    -g html2 \
#    -o /local/out/html2

#docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate \
#    -i swagger.yaml
#    --generator-name html2 \
#    -o /local/out/python


docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate \
    -i /local/director_api.yaml \
    -g html2 \
    -o /local/codegen-output/html3
