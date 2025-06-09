# Install UV
ARG BUILD_IMAGE
ARG UV_VER

# Dynamically pull the UV image using the ARG version
FROM ghcr.io/astral-sh/uv:${UV_VER} AS uv_stage

# Install UV
FROM ${BUILD_IMAGE} AS base

# Copy the files from the uv_stage
COPY --from=uv_stage /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_SYSTEM_PYTHON=true
ENV UV_LINK_MODE=copy

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable

# Copy the project into the intermediate image
COPY pyproject.toml uv.lock  /app/

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

FROM ${BUILD_IMAGE}

RUN apt-get update && apt-get install git -y

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Copy the environment, but not the source code
COPY --from=base --chown=app:app /app/.venv /app/.venv
