#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/models/db_schemas/minirag/
alembic upgrade head
cd /app

exec "$@"
