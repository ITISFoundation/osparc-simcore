# director

## Usage

```bash
  # go to director folder
  cd /services/director
  # install
  pip install .
  # start director
  simcore-service-director
  # or
  python -m simcore_service_director
```

## Development

```bash
  # go to director folder
  cd /services/director
  # install with symlinks
  pip install -r requirements-dev.txt  
```

The director implements a REST API defined in __/src/simcore_service_director/.oas3/v1/openapi.yaml__.
First extend the API and validate the API before implementing any new route.

## Current status

End validation of the requests/responses is missing as some issues arose with using the openapi-core library. It seems it is not happy with referencing a json schema file. An issue was filed to see if something may be done quickly [github](https://github.com/p1c2u/openapi-core/issues/90).

## docker

- Uses multi-stage dockerfile to extend a common stack of layers into production or development images
- Main difference between development and production stages is whether the code gets copied or not inside of the image
- Development stage is set first to avoid re-building when files are changed
- ``boot.sh`` is necessary to activate the virtual environment inside of the docker

```bash

  # development image
  docker build --target development -t director:dev .
  docker run -v %DIRECTOR_SRC_CODE:/home/scu/src director:dev

  # production image
  docker build -t director:prod .
  # or
  docker build --target production -t director:prod .
  docker run director:prod

```

### local testing

Using the main Makefile of the oSparc platform allows for testing the director:

```bash
  # go to root folder
  make build-devel
  # switch the docker swarm on in development mode
  make up-swarm-devel
```

Then open [director-swagger-ui](http://localhost:8001/apidoc/) to see the director API and try out the different routes.

## code generation from REST API "server side"

Execute the following script for generating the necessary code server side

```bash
./codegen.sh
```

NOTE: Issue #3 must still be taken care of manually!

### Issues

1. SwaggerRouter must be created with __version_ui__ set to 3 or the swagger ui must be access with ?version=3
2. SwaggerRouter.include needs to have the argument __basePath__ filled to serve the API at the right location (ndlr /v1)  [Github bug entry](https://github.com/aamalev/aiohttp_apiset/issues/45)
3. The generated models need to be manually corrected when the properties are __nullable__ as the code generator does add a check for __None__ value that triggers a ValueError exception even though the value is allowed to be null [Python server models generation issue with __nullable: true__ on GitHub](https://github.com/OpenAPITools/openapi-generator/issues/579)