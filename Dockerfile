FROM python:3.10-slim

RUN pip install poetry

WORKDIR /app

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

COPY node/ /app/node/

RUN poetry install --no-interaction --no-ansi --no-root
