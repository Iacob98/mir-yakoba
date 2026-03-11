#!/bin/bash
set -e

# Run migrations only if RUN_MIGRATIONS=true (only app service sets this)
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

echo "Starting: $@"
exec "$@"
