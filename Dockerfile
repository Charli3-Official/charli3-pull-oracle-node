FROM python:3.10-slim

RUN pip install poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./

COPY node/ ./node/

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

EXPOSE 8000

CMD ["python", "node/main.py", "run", "-c", "config.yml"]
