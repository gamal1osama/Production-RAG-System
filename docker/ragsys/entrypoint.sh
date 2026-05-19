#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/models/db_schemas/ragsys/
alembic upgrade head
cd /app

exec "$@"
