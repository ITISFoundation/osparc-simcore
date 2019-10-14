# simcore-director-sdk

The simcore-director-sdk is the client library needed to access the director REST Api.

It is currently available as an auto-generated python package but could be easily generated for other languages.

## Usage

pip install -v  git+https://github.com/ITISFoundation/osparc-simcore.git@master#subdirectory=packages/director-sdk/python

Instructions to use the package: [director-sdk](https://github.com/ITISFoundation/osparc-simcore/blob/master/packages/director-sdk/python/README.md)

## Example code

see [sample.py](https://github.com/ITISFoundation/osparc-simcore/blob/master/packages/director-sdk/sample.py)

## Development

No development as the code is automatically generated.

### local testing

Do the following:
1. Start the simcore stack
```bash
make build tag-version
make up-version
```
2. Execute __sample.py__ as an example
3. Observe logs

## code generation from REST API "client side"

Python: The code was generated using the __codegen.sh__ script together with __codegen_config.json__.
