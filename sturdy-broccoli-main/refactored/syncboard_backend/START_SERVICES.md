# Starting SyncBoard Services

## Quick Start

### Windows PowerShell (Run as Administrator)

```powershell
# Navigate to the backend directory
cd C:\Users\fuggl\Desktop\sturdy-broccoli-main\sturdy-broccoli-main\refactored\syncboard_backend

# Start all services (database, redis, backend, celery workers)
docker-compose up -d

# Check that services are running
docker-compose ps

# View logs if needed
docker-compose logs -f db
```

### After Docker Services Are Running

Once the database is up, you can run migrations:

```powershell
# Option 1: Run migrations inside the backend container
docker-compose exec backend alembic upgrade head

# Option 2: Run migrations from your local environment (requires Python setup)
cd C:\Users\fuggl\Desktop\sturdy-broccoli-main\sturdy-broccoli-main\refactored\syncboard_backend
alembic upgrade head
```

## Troubleshooting

### If Docker Desktop isn't running:
1. Open Docker Desktop application
2. Wait for it to fully start (whale icon should be steady, not animating)
3. Then run `docker-compose up -d`

### If you get "database connection" errors:
- Make sure Docker services are running: `docker-compose ps`
- Database should show "Up" and healthy
- Check logs: `docker-compose logs db`

### If you want to stop services:
```powershell
docker-compose down
```

### If you want to stop and remove all data:
```powershell
docker-compose down -v  # WARNING: Deletes database!
```

## Current Migration

The migration `docid_001_make_doc_id_autoincrement` needs to be applied.
This fixes the doc_id collision issue by implementing PostgreSQL SERIAL auto-increment.
