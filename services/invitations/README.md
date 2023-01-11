# invitations


``invitations`` is a service to create and validate invitations. It offers two interfaces for these operations: a CLI and a http-API .



These are some usage example using directly the executable or the docker image:

## With executable ``simcore-service-invitations``

We assume the executable ``simcore-service-invitations`` is installed. You can test by typing
```cmd
$ simcore-service-invitations --version
```
If not, use ``make install-prod``. Once installed have a look at all the possibilites
```cmd
$ simcore-service-invitations --help
```

### Setup

Create ``.env`` file
```
$ simcore-service-invitations generate-dotenv --auto-password > .env
$ set -o allexport; source .env; set +o allexport
```
and modify the ``.env`` if needed


### Creating invitations via CLI

Create an invitation for ``guest@company.com`` as
```
$ simcore-service-invitations invite guest@company.com --issuer=me
```
and will produce a link

### Validating invitations via CLI

```
$ simcore-service-invitations check http://my-invitation-link
```

### Starting HTTP API

Start it as a web app as
```
# simcore-service-invitations serve
```
and then open http://127.0.0.1:8000/dev/doc


## With docker image ``itisfoundation/invitations:latest``

Here we assume the image ``itisfoundation/invitations:latest`` is published in dockerhub. It can be tested by
```cmd
$ docker run -it itisfoundation/invitations:latest simcore-service-invitations --version
```
Otherwise, you can build the image tagged as ``local/invitations:production`` using ``make build``. Then check help
```cmd
$ docker run -it itisfoundation/invitations:latest simcore-service-invitations --help
```
### Setup

Create ``.env`` file
```
$ docker run -it itisfoundation/invitations:latest simcore-service-invitations generate-dotenv --auto-password > .env
```
and modify the ``.env`` if needed



### Creating invitations via CLI

Create an invitation for ``guest@company.com`` as
```
$ docker run -it --env-file .env  itisfoundation/invitations:latest simcore-service-invitations invite guest@company.com --issuer=me
```
and will produce a link



### Starting  HTTP API

Start it as a web app as
```
# docker run -it --env-file .env -p 8000:8000 itisfoundation/invitations:latest simcore-service-invitations serve
```
and then open http://127.0.0.1:8000/dev/doc
