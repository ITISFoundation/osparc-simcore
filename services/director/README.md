# director

## dockerfile

- Uses multi-stage dockerfile to extend a common stack of layers into production or development images
- Main difference between development and production stages is whether the code gets copied or not inside of the image
- Development stage is set first to avoid re-building when files are changed
- ``boot.sh`` is necessary to activate the virtual environment inside of the docker

```bash

  # development image
  docker build --target development -t director:dev .

  # production image
  docker build -t director:prod .
  # or
  docker build --target production -t director:prod .

```

## code generation from REST API "server side"

### simplified system

Execute the following script for generating the necessary code server side

```bash
./codegen.sh
```

NOTE: Issue #3 must still be taken care of manually!

### python flask generation with openapi 3.0.0

```docker
docker run -v C:\Users\anderegg\Documents\dev\OSPARC\gith
ub\osparc-simcore\services\director\.openapi\v1\:/local/ openapitools/openapi-generator-cli generate -i /local/director_api.yaml -g python-flask -o /
local/codegen
```

creates a structure with

```bash
/.openapi-generator/VERSION
/openapi_server/
    controllers/
    models/
    openapi/
    test/
    __init__.py
    __main__.py
    encoder.py
    util.py
    ...
```

### Issues:

1. SwaggerRouter must be created with __version_ui__ set to 3 or the swagger ui must be access with ?version=3
2. SwaggerRouter.include needs to have the argument __basePath__ filled to serve the API at the right location (ndlr /v1)  [Github bug entry](https://github.com/aamalev/aiohttp_apiset/issues/45)
3. The generated models need to be manually corrected when the properties are __nullable__ as the code generator does add a check for __None__ value that triggers a ValueError exception even though the value is allowed to be null [Python server models generation issue with __nullable: true__ on GitHub](https://github.com/OpenAPITools/openapi-generator/issues/579)