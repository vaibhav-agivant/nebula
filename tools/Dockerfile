# Image tagged nebula-claude, reconstructed from `docker history`: the official NebulaGraph dev image
# plus Node.js, Claude Code and Python tools. Building and testing need only the base image.
FROM vesoft/nebula-dev:ubuntu2204
SHELL ["/bin/bash", "-c"]
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs python3-pip && npm i -g @anthropic-ai/claude-code && pip3 install uv || true
