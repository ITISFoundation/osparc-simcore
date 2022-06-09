###  Highlights on updated libraries (only updated libraries are included)

- #packages before: 5
- #packages after : 8

|#|name|before|after|upgrade|count|packages|
|-|----|------|-----|-------|-----|--------|
|   1 | attrs                     | 21.4.0          | 20.3.0,20.2.0 | 🔥 downgrade | 2 | catalog🧪</br>datcore-adapter🧪 |
|   2 | certifi                   | 2021.10.8       | 2022.5.18.1 | **MAJOR**  | 1 | e2e🧪 |
|   3 | httpcore                  | 0.15.0          | 0.14.7,0.14.4 | 🔥 downgrade | 10 | api-server⬆️🧪</br>catalog⬆️🧪</br>datcore-adapter⬆️🧪</br>director-v2⬆️🧪</br>dynamic-sidecar⬆️</br>public-api🧪 |
|   4 | httpx                     | 0.23.0          | 0.22.0,0.21.3 | 🔥 downgrade | 10 | api-server⬆️🧪</br>catalog⬆️🧪</br>datcore-adapter⬆️🧪</br>director-v2⬆️🧪</br>dynamic-sidecar⬆️</br>public-api🧪 |
|   5 | paramiko                  | 2.10.4, 2.10.3  | 2.11.0     | *minor*    | 2 | catalog🧪</br>dynamic-sidecar⬆️ |

*Legend*: 
- ⬆️ base dependency (only services because packages are floating)
- 🧪 test dependency
- 🔧 tool dependency

## Repositroy-wide overview of libraries
- #reqs files parsed: 57

|#|name|versions-base|versions-test|versions-tool|
|-|----|-------------|-------------|-------------|
|   1 | aio-pika                  | 6.8.0, 7.2.0              | 6.8.0, 7.2.0              |                           |
|   2 | aioboto3                  |                           | 9.6.0                     |                           |
|   3 | aiobotocore               | 2.2.0                     | 2.3.0                     |                           |
|   4 | aiocache                  | 0.11.1                    | 0.11.1                    |                           |
|   5 | aiodebug                  | 2.3.0                     | 2.3.0                     |                           |
|   6 | aiodocker                 | 0.19.1, 0.21.0            | 0.21.0                    |                           |
|   7 | aiofiles                  | 0.8.0                     | 0.8.0                     |                           |
|   8 | aiohttp                   | 3.8.1                     | 3.8.1                     |                           |
|   9 | aiohttp-jinja2            | 1.5                       |                           |                           |
|  10 | aiohttp-security          | 0.4.0                     |                           |                           |
|  11 | aiohttp-session           | 2.11.0                    |                           |                           |
|  12 | aiohttp-swagger           | 1.0.16                    |                           |                           |
|  13 | aioitertools              | 0.10.0                    | 0.10.0                    |                           |
|  14 | aiopg                     | 1.3.3                     | 1.3.3                     |                           |
|  15 | aioredis                  | 2.0.1                     |                           |                           |
|  16 | aioresponses              |                           | 0.7.3                     |                           |
|  17 | aiormq                    | 3.3.1, 6.2.3              | 3.3.1, 6.2.3              |                           |
|  18 | aiosignal                 | 1.2.0                     | 1.2.0                     |                           |
|  19 | aiosmtplib                | 1.1.6                     |                           |                           |
|  20 | aiozipkin                 | 1.1.1                     |                           |                           |
|  21 | alembic                   | 1.7.4, 1.7.5, 1.7.7       | 1.7.4, 1.7.5, 1.7.7       |                           |
|  22 | anyio                     | 3.2.0, 3.2.1, 3.3.4, 3.5.0 | 3.2.1, 3.5.0              |                           |
|  23 | argon2-cffi               | 20.1.0                    |                           |                           |
|  24 | asgi-lifespan             |                           | 1.0.1                     |                           |
|  25 | asgiref                   | 3.4.1, 3.5.0              |                           |                           |
|  26 | astroid                   |                           | 2.11.5                    | 2.11.5                    |
|  27 | async-asgi-testclient     |                           | 1.4.10                    |                           |
|  28 | async-generator           | 1.10                      |                           |                           |
|  29 | async-timeout             | 4.0.1, 4.0.2              | 4.0.1, 4.0.2              |                           |
|  30 | asyncpg                   | 0.25.0                    |                           |                           |
|  31 | attrs                     | 20.2.0, 20.3.0, 21.4.0    | 20.2.0, 20.3.0, 21.4.0    |                           |
|  32 | aws-sam-translator        |                           | 1.45.0                    |                           |
|  33 | aws-xray-sdk              |                           | 2.9.0                     |                           |
|  34 | bcrypt                    | 3.2.0                     | 3.2.2                     |                           |
|  35 | beautifulsoup4            | 4.10.0                    |                           |                           |
|  36 | black                     |                           |                           | 22.3.0                    |
|  37 | bleach                    | 3.3.0                     |                           |                           |
|  38 | blosc                     | 1.10.6                    |                           |                           |
|  39 | bokeh                     | 2.4.2                     | 2.4.2                     |                           |
|  40 | boto3                     | 1.21.33                   | 1.21.21, 1.23.4           |                           |
|  41 | boto3-stubs               |                           | 1.23.9                    |                           |
|  42 | botocore                  | 1.24.21, 1.24.33          | 1.24.21, 1.26.4           |                           |
|  43 | botocore-stubs            |                           | 1.26.9                    |                           |
|  44 | bump2version              |                           |                           | 1.0.1                     |
|  45 | certifi                   | 2020.12.5, 2021.5.30, 2021.10.8 | 2020.12.5, 2021.5.30, 2021.10.8 |                           |
|  46 | cffi                      | 1.14.5, 1.15.0            | 1.14.5, 1.15.0            |                           |
|  47 | cfgv                      |                           |                           | 3.3.1                     |
|  48 | cfn-lint                  |                           | 0.60.1                    |                           |
|  49 | change-case               |                           |                           | 0.5.2                     |
|  50 | chardet                   | 3.0.4, 4.0.0              | 3.0.4, 4.0.0              |                           |
|  51 | charset-normalizer        | 2.0.6, 2.0.7, 2.0.10, 2.0.12 | 2.0.6, 2.0.10, 2.0.12     |                           |
|  52 | click                     | 8.0.3, 8.0.4, 8.1.2, 8.1.3 | 8.0.3, 8.0.4, 8.1.3       | 8.0.3, 8.0.4, 8.1.2, 8.1.3 |
|  53 | cloudpickle               | 2.0.0                     |                           |                           |
|  54 | codecov                   |                           | 2.1.12                    |                           |
|  55 | colorlog                  |                           | 6.6.0                     |                           |
|  56 | configparser              | 5.2.0                     |                           |                           |
|  57 | coverage                  |                           | 6.3.2, 6.4                |                           |
|  58 | coveralls                 |                           | 3.3.1                     |                           |
|  59 | cryptography              | 3.4.7, 36.0.2, 37.0.2     | 36.0.2, 37.0.2            |                           |
|  60 | cytoolz                   | 0.11.0                    |                           |                           |
|  61 | dask                      | 2022.4.0, 2022.5.0        |                           |                           |
|  62 | dask-gateway              | 0.9.0                     |                           |                           |
|  63 | dask-gateway-server       |                           | 2022.4.0                  |                           |
|  64 | decorator                 | 4.4.2                     |                           |                           |
|  65 | defusedxml                | 0.7.1                     |                           |                           |
|  66 | deprecated                | 1.2.13                    | 1.2.13                    |                           |
|  67 | dill                      |                           | 0.3.4, 0.3.5              | 0.3.5.1                   |
|  68 | distlib                   |                           |                           | 0.3.4                     |
|  69 | distributed               | 2022.4.0, 2022.5.0        |                           |                           |
|  70 | distro                    | 1.5.0                     | 1.7.0                     |                           |
|  71 | dnspython                 | 2.0.0, 2.1.0, 2.2.1       | 2.2.1                     |                           |
|  72 | docker                    | 5.0.2, 5.0.3              | 5.0.3                     |                           |
|  73 | docker-compose            | 1.29.1                    | 1.29.1                    |                           |
|  74 | dockerpty                 | 0.4.1                     | 0.4.1                     |                           |
|  75 | docopt                    | 0.6.2                     | 0.6.2                     |                           |
|  76 | ecdsa                     | 0.14.1                    | 0.17.0                    |                           |
|  77 | email-validator           | 1.1.1, 1.1.2, 1.1.3, 1.2.1 | 1.2.1                     |                           |
|  78 | entrypoints               | 0.3                       |                           |                           |
|  79 | et-xmlfile                | 1.1.0                     |                           |                           |
|  80 | execnet                   |                           | 1.9.0                     |                           |
|  81 | expiringdict              | 1.2.1                     |                           |                           |
|  82 | faker                     |                           | 13.7.0, 13.11.0, 13.11.1  |                           |
|  83 | fastapi                   | 0.71.0, 0.75.0, 0.75.1    |                           |                           |
|  84 | fastapi-contrib           | 0.2.11                    |                           |                           |
|  85 | fastapi-pagination        | 0.9.1                     |                           |                           |
|  86 | fastjsonschema            | 2.15.3                    |                           |                           |
|  87 | filelock                  |                           |                           | 3.7.0                     |
|  88 | flaky                     |                           | 3.7.0                     |                           |
|  89 | flask                     |                           | 2.1.2                     |                           |
|  90 | flask-cors                |                           | 3.0.10                    |                           |
|  91 | frozenlist                | 1.2.0, 1.3.0              | 1.2.0, 1.3.0              |                           |
|  92 | fsspec                    | 2022.3.0                  |                           |                           |
|  93 | future                    | 0.18.2                    | 0.18.2                    |                           |
|  94 | futures                   | 3.0.5                     |                           |                           |
|  95 | graphql-core              |                           | 3.2.1                     |                           |
|  96 | greenlet                  | 1.1.2                     | 1.1.2                     |                           |
|  97 | gunicorn                  | 20.1.0                    |                           |                           |
|  98 | h11                       | 0.12.0                    | 0.12.0                    |                           |
|  99 | h2                        | 4.1.0                     |                           |                           |
| 100 | heapdict                  | 1.0.1                     |                           |                           |
| 101 | hpack                     | 4.0.0                     |                           |                           |
| 102 | httpcore                  | 0.14.4, 0.14.7            | 0.14.4, 0.14.7            |                           |
| 103 | httptools                 | 0.2.0, 0.4.0              |                           |                           |
| 104 | httpx                     | 0.21.3, 0.22.0            | 0.21.3, 0.22.0            |                           |
| 105 | hyperframe                | 6.0.1                     |                           |                           |
| 106 | hypothesis                |                           | 6.46.3                    |                           |
| 107 | icdiff                    |                           | 2.0.5                     |                           |
| 108 | identify                  |                           |                           | 2.5.1                     |
| 109 | idna                      | 2.10, 3.3                 | 2.10, 3.3                 |                           |
| 110 | importlib-metadata        |                           | 4.11.3                    |                           |
| 111 | iniconfig                 | 1.1.1                     | 1.1.1                     |                           |
| 112 | inotify                   |                           |                           | 0.2.10                    |
| 113 | isodate                   | 0.6.1                     |                           |                           |
| 114 | isort                     |                           | 5.10.1                    | 5.10.1                    |
| 115 | itsdangerous              | 1.1.0, 2.1.2              | 2.1.2                     |                           |
| 116 | jaeger-client             | 4.8.0                     |                           |                           |
| 117 | jinja-app-loader          | 1.0.2                     |                           |                           |
| 118 | jinja2                    | 2.11.3, 3.1.1, 3.1.2      | 2.11.3, 3.1.1             | 3.1.1                     |
| 119 | jmespath                  | 1.0.0                     | 1.0.0                     |                           |
| 120 | jschema-to-python         |                           | 1.2.3                     |                           |
| 121 | json2html                 | 1.3.0                     |                           |                           |
| 122 | jsondiff                  | 2.0.0                     | 2.0.0                     |                           |
| 123 | jsonpatch                 |                           | 1.32                      |                           |
| 124 | jsonpickle                |                           | 2.2.0                     |                           |
| 125 | jsonpointer               |                           | 2.3                       |                           |
| 126 | jsonschema                | 3.2.0, 4.5.1              | 3.2.0, 4.5.1              |                           |
| 127 | junit-xml                 |                           | 1.9                       |                           |
| 128 | jupyter-client            | 6.1.12                    |                           |                           |
| 129 | jupyter-core              | 4.7.1                     |                           |                           |
| 130 | jupyter-server            | 1.16.0                    |                           |                           |
| 131 | jupyter-server-proxy      | 3.2.1                     |                           |                           |
| 132 | jupyterlab-pygments       | 0.1.2                     |                           |                           |
| 133 | lazy-object-proxy         | 1.4.3                     | 1.4.3, 1.7.1              | 1.7.1                     |
| 134 | locket                    | 0.2.1, 1.0.0              |                           |                           |
| 135 | lz4                       | 4.0.0                     |                           |                           |
| 136 | mako                      | 1.1.5, 1.2.0              | 1.1.5, 1.2.0              |                           |
| 137 | markupsafe                | 1.1.1, 2.0.1, 2.1.1       | 1.1.1, 2.0.1, 2.1.1       | 2.1.1                     |
| 138 | mccabe                    |                           | 0.7.0                     | 0.7.0                     |
| 139 | minio                     | 7.0.4                     | 7.0.4                     |                           |
| 140 | mistune                   | 0.8.4                     |                           |                           |
| 141 | moto                      |                           | 3.1.9                     |                           |
| 142 | msgpack                   | 1.0.3                     |                           |                           |
| 143 | multidict                 | 5.1.0, 5.2.0, 6.0.2       | 5.1.0, 5.2.0, 6.0.2       |                           |
| 144 | mypy                      |                           |                           | 0.960                     |
| 145 | mypy-extensions           |                           |                           | 0.4.3                     |
| 146 | nbclient                  | 0.5.3                     |                           |                           |
| 147 | nbconvert                 | 6.4.5                     |                           |                           |
| 148 | nbformat                  | 5.3.0                     |                           |                           |
| 149 | nest-asyncio              | 1.5.1                     |                           |                           |
| 150 | networkx                  | 2.5.1                     | 2.8.1                     |                           |
| 151 | nodeenv                   |                           |                           | 1.6.0                     |
| 152 | nose                      |                           |                           | 1.3.7                     |
| 153 | numpy                     | 1.22.3                    | 1.22.3                    |                           |
| 154 | openapi-core              | 0.12.0                    |                           |                           |
| 155 | openapi-schema-validator  | 0.2.3                     | 0.2.3                     |                           |
| 156 | openapi-spec-validator    | 0.4.0                     | 0.4.0                     |                           |
| 157 | openpyxl                  | 3.0.9                     |                           |                           |
| 158 | opentracing               | 2.4.0                     |                           |                           |
| 159 | orjson                    | 3.4.8, 3.5.4, 3.6.7, 3.6.8 |                           |                           |
| 160 | packaging                 | 20.4, 20.9, 21.0, 21.3    | 20.4, 20.9, 21.0, 21.3    |                           |
| 161 | pamqp                     | 2.3.0, 3.1.0              | 2.3.0, 3.1.0              |                           |
| 162 | pandas                    | 1.2.4                     | 1.4.2                     |                           |
| 163 | pandocfilters             | 1.4.3                     |                           |                           |
| 164 | paramiko                  | 2.11.0                    | 2.10.4, 2.11.0            |                           |
| 165 | parfive                   | 1.5.1                     |                           |                           |
| 166 | partd                     | 1.2.0                     |                           |                           |
| 167 | passlib                   | 1.7.4                     | 1.7.4                     |                           |
| 168 | pathspec                  |                           |                           | 0.9.0                     |
| 169 | pbr                       |                           | 5.9.0                     |                           |
| 170 | pennsieve                 | 6.1.2                     |                           |                           |
| 171 | pep517                    |                           |                           | 0.12.0                    |
| 172 | pillow                    | 9.0.1                     | 9.1.0                     |                           |
| 173 | pint                      | 0.19.1, 0.19.2            | 0.19.2                    |                           |
| 174 | pip-tools                 |                           |                           | 6.6.2                     |
| 175 | platformdirs              |                           | 2.5.2                     | 2.5.2                     |
| 176 | pluggy                    | 1.0.0                     | 1.0.0                     |                           |
| 177 | pprintpp                  |                           | 0.4.0                     |                           |
| 178 | pre-commit                |                           |                           | 2.19.0                    |
| 179 | prometheus-client         | 0.11.0, 0.13.1, 0.14.1    |                           |                           |
| 180 | protobuf                  | 3.20.0                    |                           |                           |
| 181 | psutil                    | 5.8.0, 5.9.0              |                           |                           |
| 182 | psycopg2-binary           | 2.8.6, 2.9.1, 2.9.2, 2.9.3 | 2.8.6, 2.9.2, 2.9.3       |                           |
| 183 | ptvsd                     |                           | 4.3.2                     |                           |
| 184 | ptyprocess                | 0.7.0                     |                           |                           |
| 185 | py                        | 1.11.0                    | 1.11.0                    |                           |
| 186 | py-cpuinfo                |                           | 8.0.0                     |                           |
| 187 | pyasn1                    | 0.4.8                     | 0.4.8                     |                           |
| 188 | pycparser                 | 2.20, 2.21                | 2.20, 2.21                |                           |
| 189 | pydantic                  | 1.9.0                     | 1.9.0                     |                           |
| 190 | pyftpdlib                 |                           | 1.5.6                     |                           |
| 191 | pygments                  | 2.9.0                     |                           |                           |
| 192 | pyinstrument              | 3.4.2, 4.0.3, 4.1.1       | 4.1.1                     |                           |
| 193 | pyinstrument-cext         | 0.2.4                     |                           |                           |
| 194 | pylint                    |                           | 2.13.8, 2.13.9            | 2.13.9                    |
| 195 | pynacl                    | 1.4.0                     | 1.5.0                     |                           |
| 196 | pyopenssl                 |                           | 22.0.0                    |                           |
| 197 | pyparsing                 | 2.4.7, 3.0.7, 3.0.8, 3.0.9 | 2.4.7, 3.0.7, 3.0.8, 3.0.9 |                           |
| 198 | pyrsistent                | 0.17.3, 0.18.0, 0.18.1    | 0.18.1                    |                           |
| 199 | pytest                    | 7.1.2                     | 7.1.2                     |                           |
| 200 | pytest-aiohttp            |                           | 1.0.4                     |                           |
| 201 | pytest-asyncio            |                           | 0.18.3                    |                           |
| 202 | pytest-benchmark          |                           | 3.4.1                     |                           |
| 203 | pytest-cov                |                           | 3.0.0                     |                           |
| 204 | pytest-docker             |                           | 0.12.0                    |                           |
| 205 | pytest-forked             |                           | 1.4.0                     |                           |
| 206 | pytest-icdiff             |                           | 0.5                       |                           |
| 207 | pytest-instafail          |                           | 0.4.2                     |                           |
| 208 | pytest-lazy-fixture       |                           | 0.6.3                     |                           |
| 209 | pytest-localftpserver     |                           | 1.1.3                     |                           |
| 210 | pytest-mock               |                           | 3.7.0                     |                           |
| 211 | pytest-runner             |                           | 6.0.0                     |                           |
| 212 | pytest-sugar              |                           | 0.9.4                     |                           |
| 213 | pytest-xdist              |                           | 2.5.0                     |                           |
| 214 | python-dateutil           | 2.8.1, 2.8.2              | 2.8.1, 2.8.2              |                           |
| 215 | python-dotenv             | 0.15.0, 0.18.0, 0.19.0, 0.20.0 | 0.15.0, 0.18.0, 0.19.0, 0.20.0 |                           |
| 216 | python-engineio           | 3.14.2                    |                           |                           |
| 217 | python-jose               | 3.2.0                     | 3.3.0                     |                           |
| 218 | python-magic              | 0.4.25                    |                           |                           |
| 219 | python-multipart          | 0.0.5                     |                           |                           |
| 220 | python-socketio           | 4.6.1                     |                           |                           |
| 221 | pytz                      | 2020.1, 2022.1            | 2022.1                    |                           |
| 222 | pyyaml                    | 5.4.1, 6.0                | 5.4.1, 6.0                | 5.4.1, 6.0                |
| 223 | pyzmq                     | 22.1.0                    |                           |                           |
| 224 | redis                     | 4.3.1                     | 4.3.1                     |                           |
| 225 | requests                  | 2.25.1, 2.26.0, 2.27.1    | 2.25.1, 2.26.0, 2.27.1    |                           |
| 226 | responses                 |                           | 0.20.0                    |                           |
| 227 | respx                     |                           | 0.19.2                    |                           |
| 228 | rfc3986                   | 1.4.0, 1.5.0              | 1.4.0, 1.5.0              |                           |
| 229 | rsa                       | 4.0                       | 4.8                       |                           |
| 230 | s3fs                      | 2022.3.0                  |                           |                           |
| 231 | s3transfer                | 0.5.2                     | 0.5.2                     |                           |
| 232 | sarif-om                  |                           | 1.0.4                     |                           |
| 233 | semantic-version          | 2.9.0                     |                           |                           |
| 234 | semver                    | 2.13.0                    |                           |                           |
| 235 | send2trash                | 1.7.1                     |                           |                           |
| 236 | setproctitle              | 1.2.3                     |                           |                           |
| 237 | simpervisor               | 0.4                       |                           |                           |
| 238 | six                       | 1.15.0, 1.16.0            | 1.15.0, 1.16.0            | 1.15.0, 1.16.0            |
| 239 | sniffio                   | 1.2.0                     | 1.2.0                     |                           |
| 240 | sortedcontainers          | 2.4.0                     | 2.4.0                     |                           |
| 241 | soupsieve                 | 2.3.2                     |                           |                           |
| 242 | sqlalchemy                | 1.4.31, 1.4.32, 1.4.36    | 1.4.31, 1.4.32, 1.4.36    |                           |
| 243 | sshpubkeys                |                           | 3.3.1                     |                           |
| 244 | starlette                 | 0.17.1                    |                           |                           |
| 245 | strict-rfc3339            | 0.7                       |                           |                           |
| 246 | tblib                     | 1.7.0                     |                           |                           |
| 247 | tenacity                  | 6.3.1, 7.0.0, 8.0.1       | 8.0.1                     |                           |
| 248 | termcolor                 |                           | 1.1.0                     |                           |
| 249 | terminado                 | 0.10.1                    |                           |                           |
| 250 | testpath                  | 0.5.0                     |                           |                           |
| 251 | texttable                 | 1.6.3                     | 1.6.4                     |                           |
| 252 | threadloop                | 1.0.2                     |                           |                           |
| 253 | thrift                    | 0.13.0, 0.15.0, 0.16.0    |                           |                           |
| 254 | toml                      |                           |                           | 0.10.2                    |
| 255 | tomli                     | 2.0.1                     | 2.0.1                     | 2.0.1                     |
| 256 | toolz                     | 0.11.1, 0.11.2            |                           |                           |
| 257 | tornado                   | 6.1                       | 6.1                       |                           |
| 258 | tqdm                      | 4.62.3, 4.63.1, 4.64.0    | 4.64.0                    |                           |
| 259 | traitlets                 | 5.1.1                     | 5.1.1                     |                           |
| 260 | typer                     | 0.4.1                     | 0.4.1                     | 0.4.1                     |
| 261 | types-aiofiles            |                           | 0.8.8                     |                           |
| 262 | types-boto3               |                           | 1.0.2                     |                           |
| 263 | types-pkg-resources       |                           | 0.1.3                     |                           |
| 264 | types-pyyaml              |                           | 6.0.7                     |                           |
| 265 | typing-extensions         | 3.10.0.2, 4.1.1, 4.2.0    | 3.10.0.2, 4.1.1, 4.2.0    | 3.10.0.2, 4.1.1, 4.2.0    |
| 266 | ujson                     | 4.0.2, 4.3.0, 5.1.0, 5.2.0 |                           |                           |
| 267 | urllib3                   | 1.26.6, 1.26.7, 1.26.9    | 1.26.6, 1.26.7, 1.26.9    |                           |
| 268 | uvicorn                   | 0.15.0, 0.17.0, 0.17.6    |                           |                           |
| 269 | uvloop                    | 0.14.0, 0.15.2, 0.16.0    |                           |                           |
| 270 | virtualenv                |                           |                           | 20.14.1                   |
| 271 | watchdog                  | 2.1.5                     |                           | 2.1.8                     |
| 272 | watchgod                  | 0.6, 0.7, 0.8.1, 0.8.2    |                           |                           |
| 273 | webencodings              | 0.5.1                     |                           |                           |
| 274 | websocket-client          | 0.59.0, 1.3.2             | 0.59.0, 1.3.2             |                           |
| 275 | websockets                | 10.1, 10.2                | 10.3                      |                           |
| 276 | werkzeug                  | 2.0.3, 2.1.2              | 2.1.2                     |                           |
| 277 | wheel                     |                           |                           | 0.37.1                    |
| 278 | wrapt                     | 1.14.0, 1.14.1            | 1.14.0, 1.14.1            | 1.14.1                    |
| 279 | xmltodict                 |                           | 0.13.0                    |                           |
| 280 | yarl                      | 1.5.1, 1.6.3, 1.7.2       | 1.5.1, 1.6.3, 1.7.2       |                           |
| 281 | zict                      | 2.0.0, 2.2.0              |                           |                           |
| 282 | zipp                      |                           | 3.8.0                     |                           |
