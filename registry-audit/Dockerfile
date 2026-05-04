FROM python:3.12-alpine

RUN pip install --no-cache-dir requests

COPY registry_audit.py /usr/local/bin/registry_audit.py

ENTRYPOINT ["python3", "/usr/local/bin/registry_audit.py"]
