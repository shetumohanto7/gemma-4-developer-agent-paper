# read-only exploration sandbox
FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ripgrep \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 agent
USER agent
WORKDIR /workspace
