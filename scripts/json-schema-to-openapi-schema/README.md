# json-schema-to-openapi-schema

This tool is based on [Phil Sturgeon blog](https://philsturgeon.uk/api/2018/04/13/openapi-and-json-schema-divergence-solved/) and specifically on [json-schema-to-openapi-schema](https://github.com/wework/json-schema-to-openapi-schema)

The tool converts any .json file present in a specific input folder into openapi schema .yaml in a specific output folder

```bash
make build
docker run -v ${INPUT_FOLDER}:/input -v ${INPUT_FOLDER}:/output json-schema-to-openapi-schema
```
