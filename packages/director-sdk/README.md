# simcore-director-sdk

The simcore-director-sdk is the client library needed to access the director REST Api.

It is currently available as an auto-generated python package but could be easily generated for other languages.

## Usage

pip install -v  git+https://github.com/ITISFoundation/osparc-simcore.git@director-sdk#subdirectory=packages/director-sdk/python

## Development

No development as the code is automatically generated.

### local testing

Do the following:
1. Start the oSparc swarm
```bash
make build
make up-swarm
```
2. Execute __sample.py__ as an example
3. Observe logs

## code generation from REST API "client side"

Python: The code was generated using the __codegen.sh__ script together with __codegen_config.json__.