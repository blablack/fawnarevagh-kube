# Build stage: diffq (a dependency of audio-separator) has no wheel for this Python and
# compiles a C extension, so gcc is needed here but not in the final image.
FROM python:3.13-slim AS build

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev


FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    DRUMLESS_DATA=/data \
    HOME=/tmp \
    NUMBA_CACHE_DIR=/tmp/numba

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Same base image and path as the build stage, so the venv's interpreter symlinks resolve.
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY drumless_web ./drumless_web

# uid/gid 1000 matches the other NFS-writing apps (matchering PUID/PGID) so files on nasio are owned consistently.
RUN groupadd --gid 1000 drumless && useradd --uid 1000 --gid 1000 drumless && mkdir /data && chown 1000:1000 /data
USER 1000:1000

EXPOSE 8000
CMD ["uvicorn", "drumless_web.app:app", "--host", "0.0.0.0", "--port", "8000"]
