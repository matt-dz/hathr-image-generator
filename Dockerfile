FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
FROM base AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

FROM base AS final
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY . .
ENV IMAGE_DIR=/tmp
ENV FONT_PATH=/app/assets/fonts/NeueHaasDisplayBold.ttf
EXPOSE 8000
WORKDIR /app/src
CMD ["uvicorn", "image_generator.main:app", "--host", "0.0.0.0", "--port", "8000"]
