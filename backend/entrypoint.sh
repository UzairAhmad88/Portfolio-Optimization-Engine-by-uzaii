#!/bin/sh
set -e

# Wait for PostgreSQL database connectivity
if [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Waiting for database connection..."
    python -c "
import sys, time
from sqlalchemy import create_engine, text
from app.db.session import get_database_url

url = get_database_url()
redacted_url = url.split('@')[-1] if '@' in url else url
print(f'[entrypoint] Probing database host: {redacted_url}')

max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('[entrypoint] Database connection verified.')
        sys.exit(0)
    except Exception as exc:
        if attempt == max_attempts:
            print(f'[entrypoint] FATAL: Unable to reach database after {max_attempts} attempts: {exc}')
            sys.exit(1)
        time.sleep(1)
"
fi

# Run database migrations if RUN_MIGRATIONS is set to true
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Running database migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "[entrypoint] Database schema is up to date."
fi

exec "$@"
