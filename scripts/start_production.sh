#!/bin/bash
set -e

echo "Starting Zinnia Axion Backend (Production Mode)"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn --config gunicorn_config.py wsgi:application
