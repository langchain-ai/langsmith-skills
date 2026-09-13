FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_MAJOR=20

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq \
    && curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# Install the langsmith CLI the same way the skills under test tell users to.
# Latest is deliberate: the eval should exercise the CLI a real user would get.
# Docker layer caching would freeze this, so runs that care pass harbor's
# --force-build (see evals/run.py --fresh-env).
RUN curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh \
    && (command -v langsmith >/dev/null || (echo "langsmith CLI not on PATH" && exit 1)) \
    && langsmith --version | tee /opt/langsmith-cli-version.txt

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

WORKDIR /workspace
COPY support_app /workspace/support_app
COPY test_cases.json /workspace/test_cases.json

CMD ["python"]
