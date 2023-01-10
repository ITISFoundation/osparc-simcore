# invitations


``invitations`` is a service that can create invitations via CLI or via an http API .


## Setup

Create ``.env`` file
```
$ make install-ci
$ simcore-service-invitations generate-dotenv > .env
```
and modify the ``.env`` if needed


## Creating invitations via CLI

1. create a invitation for ``guest@company.com`` as
```
$ simcore-service-invitations invite guest@company.com --issuer=me
```
and will produce a link



## Invitations via HTTP API

start it as a web app as
```
# simcore-service-invitations serve
```
and then open http://127.0.0.1:8000/dev/doc
