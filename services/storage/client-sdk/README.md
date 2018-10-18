# storage/client-sdk

The storage/client-sdkis the client library needed to access the director REST Api.

It is currently available as an auto-generated python package but could be easily generated for other languages.

## Usage

```cmd
    pip install -v  git+https://github.com/ITISFoundation/osparc-simcore.git@master#subdirectory=services/storage/client-sdk/python
```
Instructions to use the package: [storage/client-sdk](https://github.com/ITISFoundation/osparc-simcore/blob/master/services/storage/client-sdk/python/README.md)

## Example code

see [sample.py](https://github.com/ITISFoundation/osparc-simcore/blob/master/services/storage/client-sdk/sample.py)

## Development

No development as the code is automatically generated.

### local testing

Do the following:
1. Start the oSparc swarm
```bash
make build
make up-swarm
```
1. Execute __sample.py__ as an example
1. Observe logs

## code generation from REST API "client side"

Python: The code was generated using the __codegen.sh__ script together with __codegen_config.json__.
