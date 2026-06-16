FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/
RUN cd frontend && npm install
COPY frontend ./frontend
RUN cd frontend && npm run build

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY --from=frontend /build/app/static ./app/static

RUN mkdir -p /app/data
