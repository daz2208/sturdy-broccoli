# Windows Setup Guide

## Quick Start (Windows)

### Option 1: PowerShell (Recommended)
```powershell
# Start services
.\start-dev.ps1

# Stop services
.\stop-dev.ps1
```

### Option 2: Command Prompt / Batch
```cmd
# Start services
start-dev.bat

# Stop services
stop-dev.bat
```

## Important Notes for Windows Users

### Script Files
- **PowerShell scripts** (`.ps1`): Modern, feature-rich, recommended for Windows 10/11
- **Batch scripts** (`.bat`): Compatible with all Windows versions, simpler functionality
- **Bash scripts** (`.sh`): For Linux/WSL only - **DO NOT USE** on native Windows

### PowerShell Execution Policy
If you get an error running `.ps1` scripts, you may need to allow script execution:

```powershell
# Run PowerShell as Administrator and execute:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try running `.\start-dev.ps1` again.

### Docker Desktop
Make sure Docker Desktop is running before starting the services.

### File Paths
Windows uses backslashes (`\`) for paths, but Docker and most development tools work fine with forward slashes (`/`). The scripts handle this automatically.

## Troubleshooting

### Docker not starting
- Make sure Docker Desktop is running
- Check that virtualization is enabled in BIOS
- Ensure WSL2 is installed if using WSL2 backend

### Port conflicts
If ports 8000, 5432, 6379, or 5555 are already in use:
```cmd
# Find what's using a port
netstat -ano | findstr :8000

# Kill process by PID
taskkill /PID <pid> /F
```

### Connection issues
See `DOCKER_WSL_TROUBLESHOOTING.md` for detailed troubleshooting steps.

## What Each Script Does

### start-dev (.ps1 / .bat)
1. Checks if Docker is running
2. Creates `.env` from `.env.example` if needed
3. Stops any existing containers
4. Starts all backend services (PostgreSQL, Redis, FastAPI, Celery)
5. Waits for services to be healthy
6. Shows you the URLs and next steps

### stop-dev (.ps1 / .bat)
1. Stops all Docker containers
2. Network and volumes remain intact (data preserved)

## Next Steps After Starting Backend

1. Backend should now be running at http://localhost:8000
2. Test it: Visit http://localhost:8000/docs
3. Start frontend in a **new terminal**:
   ```cmd
   cd ..\..\..\frontend
   npm install
   npm run dev
   ```
4. Open http://localhost:3000

## Manual Docker Commands (Alternative)

If you prefer to run Docker commands manually:

```cmd
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Restart a service
docker-compose restart backend
```
