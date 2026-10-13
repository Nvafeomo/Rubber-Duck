# RubberDuck in a container: runs the tests by default, and the evaluations
# through docker-compose.yml. The pre-commit demo itself runs on the host.
FROM python:3.12-slim

# git is needed by the tests, by "rubberduck review", and to clone the TinyDB corpus
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY rubberduck ./rubberduck
RUN pip install --no-cache-dir -e ".[dev]"

COPY tests ./tests
COPY evaluation ./evaluation

CMD ["pytest", "-q"]
