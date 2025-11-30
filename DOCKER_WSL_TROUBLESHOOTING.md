# Docker/WSL Frontend-Backend Connection Troubleshooting Guide

## Problem
Frontend cannot connect to backend API, resulting in 500 errors or connection failures when Docker and WSL are involved.

## Root Causes Identified

1. **Missing Environment Files**: `.env` files were not configured
2. **Docker/WSL Networking**: Network address resolution issues between Docker containers and host
3. **CORS Misconfiguration**: Backend wasn't allowing all necessary origins
4. **Port Binding Issues**: Docker port exposure not working correctly in WSL

## Solutions Applied

### 1. Environment Files Created

**Backend `.env` file** (`/refactored/syncboard_backend/.env`):
- Configured database to use Docker service name: `db:5432`
- Configured Redis to use Docker service name: `redis:6379`
- Extended CORS to allow `localhost`, `127.0.0.1`, and `host.docker.internal`

**Frontend `.env.local` file** (`/refactored/syncboard_backend/frontend/.env.local`):
- Set `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Set `NEXT_PUBLIC_WS_URL=ws://localhost:8000`

### 2. Docker Compose CORS Updated
Updated `docker-compose.yml` to allow multiple origins for Docker/WSL compatibility.

## How to Fix Your Setup

### Option 1: Run Backend in Docker, Frontend Locally (Recommended for Development)

1. **Start the backend services:**
   ```bash
   cd sturdy-broccoli-main/refactored/syncboard_backend
   docker-compose up -d
   ```

2. **Check backend is running:**
   ```bash
   # Should show 8 containers running
   docker-compose ps

   # Test backend health endpoint
   curl http://localhost:8000/health
   ```

3. **Start the frontend locally:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Flower (Celery Monitor): http://localhost:5555

### Option 2: Run Everything in Docker

1. **Create a Docker Compose override for frontend:**
   ```bash
   cd sturdy-broccoli-main/refactored/syncboard_backend
   ```

2. **Add this to `docker-compose.yml` (or create `docker-compose.override.yml`):**
   ```yaml
   services:
     frontend:
       build:
         context: ./frontend
         dockerfile: Dockerfile
       container_name: syncboard-frontend
       restart: unless-stopped
       ports:
         - "3000:3000"
       environment:
         NEXT_PUBLIC_API_URL: http://backend:8000
         NEXT_PUBLIC_WS_URL: ws://backend:8000
       depends_on:
         - backend
       networks:
         - syncboard-network
   ```

3. **Start everything:**
   ```bash
   docker-compose up -d
   ```

### Option 3: WSL-Specific Fixes

If you're running Docker in WSL and having network issues:

1. **Update frontend `.env.local` to use `127.0.0.1`:**
   ```bash
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000
   ```

2. **Or use WSL's IP address:**
   ```bash
   # Get WSL IP
   hostname -I

   # Update .env.local with the WSL IP
   NEXT_PUBLIC_API_URL=http://<WSL_IP>:8000
   ```

3. **Check Docker port bindings:**
   ```bash
   docker-compose ps
   # Ensure ports are mapped: 0.0.0.0:8000->8000/tcp
   ```

## Common Issues and Fixes

### Issue 1: "ERR_CONNECTION_REFUSED" on port 8000

**Diagnosis:**
```bash
# Check if backend container is running
docker ps | grep syncboard-backend

# Check backend logs
docker logs syncboard-backend

# Check if port is accessible
curl http://localhost:8000/health
```

**Fix:**
```bash
# Restart backend
cd sturdy-broccoli-main/refactored/syncboard_backend
docker-compose restart backend

# Or rebuild if there are code changes
docker-compose up -d --build backend
```

### Issue 2: 500 Internal Server Error

**Diagnosis:**
```bash
# Check backend logs for errors
docker logs syncboard-backend --tail 100

# Check if database is ready
docker logs syncboard-db --tail 50
```

**Common causes:**
- Database not ready when backend starts
- Missing environment variables
- Database migration not run

**Fix:**
```bash
# Run migrations manually
docker exec syncboard-backend alembic upgrade heads

# Restart backend
docker-compose restart backend
```

### Issue 3: CORS Errors in Browser Console

**Error:** `Access to XMLHttpRequest at 'http://localhost:8000/...' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Fix:**
1. Check `.env` file has proper CORS origins
2. Restart backend: `docker-compose restart backend`
3. Clear browser cache and reload

### Issue 4: Docker Containers Won't Start

**Diagnosis:**
```bash
# Check what's wrong
docker-compose ps
docker-compose logs
```

**Fix:**
```bash
# Stop everything
docker-compose down

# Remove volumes if database is corrupted (WARNING: loses data)
docker-compose down -v

# Rebuild and start fresh
docker-compose up -d --build
```

### Issue 5: WSL Network Not Working

**Fix:**
```bash
# Restart WSL
wsl --shutdown
# Then reopen WSL

# Restart Docker Desktop
# In Windows: Restart Docker Desktop application

# Check Docker is running in WSL
docker ps
```

## Verification Steps

After applying fixes, verify everything works:

1. **Backend Health Check:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"ok"}
   ```

2. **Check all containers are running:**
   ```bash
   docker-compose ps
   # Should show 8-9 containers all "Up"
   ```

3. **Test frontend-backend connection:**
   - Open http://localhost:3000
   - Open browser dev tools (F12)
   - Check Network tab for successful API calls
   - Should see 200 OK responses from `http://localhost:8000`

4. **Check logs for errors:**
   ```bash
   # Backend logs
   docker logs syncboard-backend --tail 50

   # Database logs
   docker logs syncboard-db --tail 50

   # Redis logs
   docker logs syncboard-redis --tail 50
   ```

## Quick Reset (Nuclear Option)

If nothing works, do a complete reset:

```bash
cd sturdy-broccoli-main/refactored/syncboard_backend

# Stop and remove everything
docker-compose down -v

# Remove all images (optional)
docker-compose down --rmi all

# Remove node_modules and reinstall (frontend)
cd frontend
rm -rf node_modules .next
npm install

# Start fresh
cd ..
docker-compose up -d --build

# Wait for services to be ready (30-60 seconds)
sleep 30

# Check health
curl http://localhost:8000/health

# Start frontend
cd frontend
npm run dev
```

## Docker Desktop WSL Integration

If using Docker Desktop on Windows with WSL:

1. **Enable WSL Integration:**
   - Open Docker Desktop
   - Settings → Resources → WSL Integration
   - Enable integration for your WSL distro

2. **Check Docker is accessible in WSL:**
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Use WSL file system for better performance:**
   - Clone repo in WSL: `/home/user/...`
   - NOT in Windows mount: `/mnt/c/...`

## Network Debugging Commands

```bash
# Check what ports are listening
netstat -tulpn | grep LISTEN

# Check if port 8000 is accessible
nc -zv localhost 8000

# Check Docker network
docker network ls
docker network inspect syncboard-network

# Check container networking
docker exec syncboard-backend ping db
docker exec syncboard-backend ping redis

# Check from Windows (if using WSL)
# In PowerShell:
Test-NetConnection -ComputerName localhost -Port 8000
```

## Environment Variable Debugging

```bash
# Check environment variables in backend container
docker exec syncboard-backend env | grep SYNCBOARD

# Check if CORS origins are set correctly
docker exec syncboard-backend env | grep ALLOWED_ORIGINS
```

## Still Not Working?

1. **Check firewall:** Windows Firewall or WSL firewall might be blocking ports
2. **Check antivirus:** Some antivirus software blocks Docker networking
3. **Try different port:** Change backend to 8001 in docker-compose.yml and .env files
4. **Check WSL version:** `wsl --list --verbose` (should be WSL 2)
5. **Update Docker Desktop:** Make sure you have the latest version

## Success Indicators

You'll know everything is working when:
- ✅ `curl http://localhost:8000/health` returns `{"status":"ok"}`
- ✅ `docker-compose ps` shows all containers "Up"
- ✅ Frontend at http://localhost:3000 loads without errors
- ✅ Browser console shows no CORS errors
- ✅ API calls in Network tab return 200 OK
- ✅ You can login and see data in the frontend
