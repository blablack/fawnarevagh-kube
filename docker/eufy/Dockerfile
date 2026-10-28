FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    EUFY_DATA=/data

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev && pip uninstall -y uv

COPY eufy_fix ./eufy_fix
COPY eufy_web ./eufy_web
COPY eufy_map.py ./

RUN useradd --uid 10001 --create-home eufy && mkdir /data && chown 10001 /data
USER 10001

EXPOSE 8000
CMD ["uvicorn", "eufy_web.app:app", "--host", "0.0.0.0", "--port", "8000"]
