# simcore-webserver-sdk

The simcore-webserver-sdk is the client library needed to access the webserver REST Api.

It is currently available as an auto-generated python package but could be easily generated for other languages.

## Usage

```bash
pip install -v  git+https://github.com/ITISFoundation/osparc-simcore.git@webserver-sdk#subdirectory=packages/webserver-sdk/python

```

## Development

start server
```bash
cd osparc-simcore
make .venv
source .venv/bin/activate

# install
cd ospac-simcore/services/web/server
pip install -r requirements/dev.txt

# starts server
cat tests/mock/configs/minimum.yaml
simcore-services-webserver -c tests/mock/configs/minimum.yaml
```

run client
```bash
cd osparc-simcore
source .venv/bin/activate

cd ospac-simcore/packages/webserver-sdk
pip install -e .

# runs a small example
python sample.py
```
