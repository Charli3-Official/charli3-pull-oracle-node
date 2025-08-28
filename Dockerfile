FROM python:3.10.4-slim-buster

RUN pip install poetry

WORKDIR /app

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

COPY node/ /app/node/

RUN poetry install --no-interaction --no-ansi --no-root

CMD ["python", "-m", "node.main", "run", "-c", "config.yml"]
