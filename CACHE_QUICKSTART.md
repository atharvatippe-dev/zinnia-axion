# Quick Start: Testing Database Optimization

## Prerequisites

You should have:
- Backend running on `http://localhost:5000`
- PostgreSQL database configured
- Python 3.10+
- `redis-cli` available (or Redis Docker container)

## Step 1: Start Redis

### Option A: Homebrew (macOS)
```bash
brew install redis
redis-server
# In another terminal: redis-cli ping
# Expected: PONG
```

### Option B: Docker
```bash
docker run -d -p 6379:6379 redis:latest
# Test: redis-cli ping
```

### Option C: Already installed
```bash
redis-server
```

## Step 2: Verify Configuration

Check that `.env` has cache settings:
```bash
grep -A 10 "Redis Cache Configuration" .env
```

Should see:
```
CACHE_ENABLED=true
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Step 3: Start Backend

```bash
cd /Users/Zinnia_India/Desktop/zinnia-axion
python -m backend.app
```

Check the logs for:
```
Redis cache connected successfully
CloudWatch client initialized
```

## Step 4: Test Cache & Metrics

### Get Current Metrics
```bash
curl http://localhost:5000/metrics | python -m json.tool
```

Expected response:
```json
{
  "timestamp": "2025-03-04T10:30:45.123456",
  "database": {
    "pool_size": 10,
    "pool_checked_out": 3,
    "pool_idle": 7,
    "pool_overflow": 0
  },
  "cache": {
    "status": "connected",
    "used_memory_mb": 45.2,
    "hit_rate": 78.5,
    "keyspace_hits": 15234,
    "keyspace_misses": 4107
  }
}
```

### Trigger Metrics Report to CloudWatch
```bash
curl -X POST http://localhost:5000/metrics/report | python -m json.tool
```

### Monitor Cache Activity
```bash
redis-cli MONITOR
```

Then make API requests. You should see Redis commands like `SETEX`, `GET`, `DEL`.

## Step 5: Test Caching in Action

### Check Cache Hit Rate Improves

```bash
# First request (cache miss)
curl http://localhost:5000/summary/today?user_id=Atharva

# Second request (cache hit - should be faster)
curl http://localhost:5000/summary/today?user_id=Atharva
```

Watch Redis cache stats:
```bash
redis-cli INFO stats | grep keyspace
```

Hit rate should increase on repeated requests.

## Step 6: Database Indexing Verification

Check that indexes were created:

```bash
# Using psql (if PostgreSQL)
psql telemetry_db -U telemetry_user -c "\d+ telemetry_events"
```

Should see indexes:
- `ix_telemetry_user_timestamp`
- `ix_telemetry_app_name`

Or in SQLite:
```bash
sqlite3 telemetry.db ".schema telemetry_events"
```

## Step 7: Connection Pool Monitoring

Monitor database connection pool:

```bash
# Get pool stats
curl http://localhost:5000/metrics | python -m json.tool | grep -A 10 database

# Should show:
# "pool_size": 10,
# "pool_checked_out": 3,  (active connections)
# "pool_idle": 7,         (idle connections)
# "pool_overflow": 0      (extra connections)
```

## Step 8: CloudWatch Integration (Optional)

If you have AWS credentials, test CloudWatch metrics:

```bash
# Set AWS credentials in environment
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1

# Restart backend
python -m backend.app

# Check logs for: "CloudWatch client initialized"

# Metrics are now being sent to CloudWatch
# View in AWS Console: CloudWatch → Metrics → ZinniaAxion/Backend
```

## Troubleshooting

### Redis Not Connecting

```bash
# Check Redis is running
redis-cli ping
# Should respond: PONG

# Check logs
python -m backend.app 2>&1 | grep -i redis
# Should see: "Redis cache connected successfully"
```

### Cache Not Working

```bash
# Check cache is enabled
redis-cli DBSIZE
# Should show: db0:keys=N

# Check cache keys
redis-cli KEYS "*"
# Should show cache keys like: user:id:1, team:hierarchy:2

# Clear cache (if needed)
redis-cli FLUSHDB
```

### Database Indexes Not Created

```bash
# For PostgreSQL
psql telemetry_db -U telemetry_user -c "\di telemetry_*"

# For SQLite
sqlite3 telemetry.db ".indices"
```

If missing, run migrations:
```bash
python -m flask db upgrade
```

### Connection Pool Issues

```bash
# Check pool configuration
grep DB_POOL .env

# Expected:
# DB_POOL_SIZE=10
# DB_POOL_RECYCLE=3600
# DB_POOL_PRE_PING=true
# DB_MAX_OVERFLOW=20
```

## Performance Comparison

### Before Optimization
```bash
time curl http://localhost:5000/summary/today
# ~2-5 seconds (depends on DB size)
```

### After Optimization (with cache)

First request (cache miss):
```bash
time curl http://localhost:5000/summary/today
# ~1-2 seconds
```

Repeated request (cache hit):
```bash
time curl http://localhost:5000/summary/today
# ~200-500ms (2-5x faster!)
```

## Files to Review

- `backend/cache_config.py` — Cache configuration and helpers
- `backend/cloudwatch_metrics.py` — CloudWatch integration
- `backend/cached_queries.py` — Cached query helpers
- `backend/monitoring.py` — Metrics collection
- `DATABASE_OPTIMIZATION_GUIDE.md` — Comprehensive documentation
- `.env` — Configuration variables

## Next Steps

1. **Local Development**: Use with Redis for faster iteration
2. **Staging**: Test cache invalidation and CloudWatch with production-like load
3. **Production Deployment**: Use AWS ElastiCache for Redis, enable CloudWatch alarms
4. **Monitoring**: Set up CloudWatch dashboard for visibility
5. **Optimization**: Adjust TTL values based on observed hit rates

## Support

For issues or questions, refer to:
1. `DATABASE_OPTIMIZATION_GUIDE.md` — Comprehensive troubleshooting guide
2. Logs from `python -m backend.app` — Check for cache/metrics initialization
3. Redis CLI (`redis-cli MONITOR`) — Watch cache activity in real-time
4. CloudWatch Console — View metrics and set up alarms
