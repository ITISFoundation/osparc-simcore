FROM python:3.9.12-buster

RUN curl https://rclone.org/install.sh | bash && \
  rclone --version

WORKDIR /scripts

COPY packages/postgres-database postgres-database
RUN cd postgres-database && pip install .

COPY scripts/maintenance/migrate_project/requirements.txt /scripts/requirements.txt
RUN pip install -r /scripts/requirements.txt

COPY scripts/maintenance/migrate_project/src/*.py /scripts/
