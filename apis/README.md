# APIs development guidelines

# Concept

REST APIs and models (defined as openAPI- or JSON-schemas) are defined in a central location (/apis) to allow for "design-first" development.

# Development guidelines

## Standards

The oSparc platform uses the following standards:
- REST API: [Open API v3](https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md)
- Models and configuration [JSON Schema](https://json-schema.org/)

## Folder structure

```bash
/apis/                                  # base folder
/apis/director/                         # service name folder (e.g. for director service)
/apis/director/v0/                      # service version (v0 for development, then v1, v2... only major)
/apis/director/v0/openapi.yaml          # openapi specifications in YAML
/apis/director/v0/schemas/              # schemas only used by the director API
/apis/director/v0/schemas/services.yaml # openapi encoded service only schema

/apis/shared/                           # shared apis/schemas base folder
/apis/shared/schemas/                   # sub folder for schemas
/apis/shared/schemas/health_check.yaml  # openapi encoded shared schema
/apis/shared/schemas/node-meta.json     # jsonschema encoded shared schema
/apis/shared/schemas/v1/error.yaml      # openapi encoded shaared schema for version 1
/apis/shared/schemas/v2/error.yaml      # openapi encoded shaared schema for version 2

/tests/                                 # python tests folder to check schemas validity
/tests/requirements.txt                 # requirements for python tests
```

## Organization

### Openapi specifications file

Each API is defined within a file __openapi.yaml__ in YAML format. The file shall be located in the a subfolder named after the service/package and the major version subfolder.

#### Version subfolder

For initial development, the version shall be 0.1.0 and the subfolder v0
For release, the version shall start from 1.0.0 and subfolder v1.
The subolder digit corresponds to the version major digits. It shall be modified only when changes are not backwards compatible (e.g. changing a return value, removing parameters or resource, ...).

#### Schemas in separate files

Schemas shall always be defined in separate files.

Schemas format shall be either OpenAPI v3 or JSON schema Draft#7.

If these schemas are pertinent only to the current API they shall be contained together with the openapi specifications file inside a __schemas__ subfolder.
If these schemas are shared with other APIs they should be located in the __/shared/schemas__ subfolder.

#### Versioning shared schemas

NOTE: If shared schemas need backward incompatible changes, then a new major version of this specific shared schema is necessary and all APIs that rely on this specific schema will need to be upgraded.
In that case, a version subfolder shall be added in the __/shared/__ subfolder and the relevant schemas shall be moved there.

### Schemas defined with JSONSchema format that are used together with OpenAPI

Mixing JSONSchema with OpenAPI schema needs some additional steps:

1. Define the JSONSchema schema.
2. Convert the JSONSchema formatted file to OpenAPI formatted file using the [converter](../scripts/jsonschema/openapi_converter).
3. In the openapi specifications file ref the converted OpenAPI schema file.

## Using the openAPI

### Python: Current status (using aiohttp-apiset)

The current python-based packages use the aiohttp-apiset library to create routes from the defined API. The aiohttp-apiset library requires a physical file to create the routes. Therefore one needs to generate that file by following:

1. Generate a 1 file OpenAPI formatted file using [prance](https://pypi.org/project/prance/). By using [openapi-resolver](../scripts/openapi/oas_resolver).
2. Copy the generated file in a folder in the python-based code and use it.

### Python: in development and should be available soon

Using the library [openapi-core](https://github.com/p1c2u/openapi-core) the library is able to download the api at starting point.
The [apihub service](../services/apihub) serves the apis and schemas to the internal parts of the oSparc platform.

## references

- [defining reusable components - good practices](https://dev.to/mikeralphson/defining-reusable-components-with-the-openapi-specification-4077)
- [official guidelines on OAS re-usability](https://github.com/OAI/OpenAPI-Specification/blob/master/guidelines/v2.0/REUSE.md)