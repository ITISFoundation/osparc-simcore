# APIs development guidelines

# Concept

Common REST API specifications and models (defined as openAPI- or JSON-schemas) are defined in a central location [``api/specs``](/api/specs) to allow for **design-first development**.

# Standards

The oSparc platform uses the following standards:
- [Open API v3](https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md) for REST API
- [JSONSchema] for models and configuration schemas

## In every service:

  The api is defined in

  - ``/api/Makefile`` bundles oas-parts into openapi.yaml and validates it
  - ``/api/v0``
    - ``/api/v0/openapi.yaml`` is the output of api/Makefile. DO NOT EDIT MANUALLY. Use instead Makefile
    - ``/api/v0/oas-parts/*`` folder contains all parts of the open-api specs as well as json schemas of models. This is the folder that the user shall modify.


## In common folder:

```bash
/api/specs/                                  # base folder

/api/specs/common/                           # common api/specs/schemas base folder
/api/specs/common/schemas/                   # sub folder for schemas
/api/specs/common/schemas/health_check.yaml  # openapi encoded common schema
/api/specs/common/schemas/node-meta.json     # jsonschema encoded common schema
/api/specs/common/schemas/v1/error.yaml      # openapi encoded common schema for version 1
/api/specs/common/schemas/v2/error.yaml      # openapi encoded common schema for version 2

/tests/                                 # python tests folder to check schemas validity
/tests/requirements.txt                 # requirements for python tests
```

## Organization

### Openapi specifications file

Each API is defined within a file __openapi.yaml__ in YAML format. The file shall be located in the a subfolder named after the service/package and the major version subfolder.

#### Version subfolder

For initial development, the version shall be 0.1.0 and the subfolder ``v0``
For release, the version shall start from 1.0.0 and subfolder v1.
The subolder digit corresponds to the version major digits. It shall be modified only when changes are not backwards compatible (e.g. changing a return value, removing parameters or resource, ...).

#### Schemas in separate files

Schemas shall always be defined in separate files.

Schemas format shall be either OpenAPI v3 or JSON schema Draft#7.

If these schemas are pertinent only to the current API they shall be contained together with the openapi specifications file inside a __schemas__ subfolder.
If these schemas are common with other APIs they should be located in the __/common/schemas__ subfolder.

#### Versioning common schemas

NOTE: If common schemas need backward incompatible changes, then a new major version of this specific common schema is necessary and all APIs that rely on this specific schema will need to be upgraded.
In that case, a version subfolder shall be added in the __/common/__ subfolder and the relevant schemas shall be moved there.

### Schemas defined with [JSONSchema] format that are used together with [OpenAPI]

Mixing [JSONSchema] with OpenAPI schema needs some additional steps:

1. Define the [JSONSchema] schema.
2. Convert the [JSONSchema] formatted file to OpenAPI formatted file using a [converter](/scripts/json-schema-to-openapi-schema) tool.
3. In the openapi specifications file ref the converted OpenAPI schema file

This is automated in the makefiles as dependencies


## references

- [Defining reusable components - good practices](https://dev.to/mikeralphson/defining-reusable-components-with-the-openapi-specification-4077)
- [Official guidelines on OAS re-usability](https://github.com/OAI/OpenAPI-Specification/blob/master/guidelines/v2.0/REUSE.md)



<!--Add links below this line-->
[JSONSchema]:https://json-schema.org/
[OpenAPI]:https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
