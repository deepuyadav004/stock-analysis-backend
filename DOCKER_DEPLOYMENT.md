# Docker & Fly.io Deployment Guide

## Overview

This directory contains the stock analysis backend application configured for Docker containerization and Fly.io deployment.

## Files Added

### 1. **Dockerfile**
Multi-stage production Dockerfile optimized for:
- **Stage 1 (Builder)**: Compiles all Python dependencies with build tools
- **Stage 2 (Runtime)**: Minimal image with only runtime dependencies
- Python 3.11 slim base image (balances size with ML package compatibility)
- PyTorch and transformers pre-compiled and cached
- Health check configured using the `/health` endpoint

### 2. **.dockerignore**
Optimizes Docker build context by excluding:
- `__pycache__` and compiled Python files
- `.git` and version control
- Build artifacts and test files
- IDE configuration
- Environment files (handled at runtime)

### 3. **fly.toml**
Fly.io deployment configuration:
- Application name: `grow-wealth-backend`
- Region: Singapore (adjust as needed)
- Service configuration with 80/443 ports
- Health check on `/health` endpoint
- Resource limits: 1 CPU, 1GB RAM (adjust for workload)

## Local Docker Testing

### Build Image
```bash
cd stock-backend
docker build -t grow-wealth-backend:latest .
```

### Run Container Locally
```bash
docker run --rm \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  -p 8000:8000 \
  grow-wealth-backend:latest
```

Test health check:
```bash
curl http://localhost:8000/health
```

## Deploying to Fly.io

### Prerequisites
1. Install Fly.io CLI: https://fly.io/docs/hands-on/install-flyctl/
2. Have a Fly.io account (free tier available)

### Step-by-Step Deployment

#### 1. Initialize (First Time Only)
```bash
cd stock-backend
flyctl auth login
flyctl launch
```

When prompted:
- Accept the generated `fly.toml` configuration (or use the one provided)
- Set app name: `grow-wealth-backend` (or your preferred name)
- Choose region: Singapore (sin) or your closest region

#### 2. Set Database Secret
Store your Supabase DATABASE_URL securely:
```bash
flyctl secrets set DATABASE_URL="postgresql://postgres.ymuauoipnzisofgsbndk:KJblmjYSMYonpbjB@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
```

Verify secrets were set:
```bash
flyctl secrets list
```

#### 3. Deploy
```bash
flyctl deploy
```

The CLI will:
- Build the Docker image
- Push to Fly.io registry
- Deploy to your configured region
- Perform health checks
- Show deployment logs

#### 4. Monitor Deployment
```bash
# View live logs
flyctl logs

# Check app status
flyctl status

# View resource usage
flyctl metrics
```

#### 5. Access Your App
Your app will be available at:
```
https://grow-wealth-backend.fly.dev
```

Test the health endpoint:
```bash
curl https://grow-wealth-backend.fly.dev/health
```

## Important Configuration Notes

### Database Connection
- **DATABASE_URL** must be set via `flyctl secrets set` before deployment
- The connection string uses Supabase's pooler endpoint (recommended)
- Ensure Supabase allows external connections (configure IP whitelist if needed)

### Environment Variables
- **PORT**: Automatically handled by Fly.io (defaults to 8000)
- **PYTHONUNBUFFERED=1**: Set in Dockerfile to ensure logs stream properly
- Add other environment variables via `flyctl secrets set VAR_NAME="value"`

### Resource Scaling
Current configuration uses shared CPU (1 vCPU, 1GB RAM). For production:
- Monitor metrics: `flyctl metrics`
- Scale up if needed: `flyctl scale vm --vm-memory=2048`
- Add more instances: `flyctl scale count 2`

### Health Checks
- Endpoint: `/health` (returns `{"status": "ok"}`)
- Interval: 30 seconds
- Timeout: 10 seconds
- Grace period: 10 seconds (time to start before checks begin)
- Failures trigger automatic restarts

## Troubleshooting

### Failed Deployment
```bash
# View detailed build logs
flyctl logs --all

# SSH into running instance for debugging
flyctl ssh console
```

### Database Connection Issues
1. Verify DATABASE_URL secret is set:
   ```bash
   flyctl secrets list
   ```
2. Check Supabase allows external connections
3. Verify connection string format

### Out of Memory
- Monitor: `flyctl metrics`
- Increase: `flyctl scale vm --vm-memory=2048`
- Check for memory leaks in models/transformation code

## Updating the App

### After Code Changes
```bash
git add .
git commit -m "Update backend logic"
flyctl deploy
```

### Clear Builds Cache
```bash
flyctl deploy --no-cache
```

## Cost Optimization

### Fly.io Free Tier Includes
- 3 shared-cpu-1x 256MB VMs
- 160GB outbound data transfer
- Paid if exceeded

### Cost Reduction
- Keep app in single region (transfers are free within region)
- Use shared CPU for lower traffic
- Only scale when necessary

## Architecture Overview

```
┌─────────────────────┐
│   Fly.io Region     │
│  ┌───────────────┐  │
│  │ Docker Image  │  │
│  │  - Python 3.11│  │
│  │  - Starlette  │  │
│  │  - Uvicorn    │  │
│  └───────────────┘  │
│     Service:        │
│   - 80 (HTTP)       │
│   - 443 (HTTPS)     │
│   - Health check    │
└─────────────────────┘
         ↓
    (Persistent)
┌──────────────────────┐
│  Supabase Database   │
│    PostgreSQL        │
└──────────────────────┘
```

## Rollback

If you need to roll back to a previous version:
```bash
flyctl releases
flyctl releases rollback <version_number>
```

## Additional Resources

- [Fly.io Documentation](https://fly.io/docs/)
- [Starlette Documentation](https://www.starlette.io/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
