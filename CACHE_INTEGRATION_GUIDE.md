# Cache Integration Guide for Blueprint Developers

This guide explains how to integrate caching and CloudWatch metrics into your Flask blueprints.

## Quick Example: Caching a User Lookup

### Before (No Cache)
```python
@some_bp.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404
    return jsonify(user.to_dict()), 200
```

### After (With Cache)
```python
from backend.cached_queries import CachedQueries

@some_bp.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    # Try cache first, fall back to database
    user_data = CachedQueries.get_user_by_id(db, user_id)
    if not user_data:
        return jsonify({"error": "Not found"}), 404
    return jsonify(user_data), 200
```

**Result**: First request queries database (~100ms), subsequent requests served from cache (~5ms)

---

## Common Caching Patterns

### 1. User Lookup (5-minute TTL)

```python
from backend.cached_queries import CachedQueries

# Get user by ID
user = CachedQueries.get_user_by_id(db, user_id)

# Get user by LAN ID
user = CachedQueries.get_user_by_lan_id(db, "john.doe")

# When user is updated, invalidate cache
CachedQueries.invalidate_user_cache(user_id)
```

### 2. Team Hierarchy (15-minute TTL)

```python
from backend.cached_queries import CachedQueries

# Get team and all descendants
team_hierarchy = CachedQueries.get_team_hierarchy(db, team_id)

# Get all teams for a user
team_ids = CachedQueries.get_user_teams(db, user_id)

# When team structure changes, invalidate
CachedQueries.invalidate_team_cache(team_id)
```

### 3. Dashboard Data (1-minute TTL)

```python
from backend.cached_queries import CachedQueries

# Check cache first
summary = CachedQueries.get_dashboard_summary(db, user_id, days=1)

# If not cached, compute and store
if summary is None:
    summary = _compute_dashboard_summary(user_id)
    # Cache will be populated on next request
```

---

## Manual Caching with Decorator

### Cache a Function's Result

```python
from backend.cache_config import cached

@cached(key_prefix="user:summary", ttl=300)
def get_user_summary(user_id):
    # This result will be cached for 5 minutes
    return db.session.query(User).get(user_id).to_dict()

# Usage
summary = get_user_summary(123)  # First call: database query
summary = get_user_summary(123)  # Second call: from cache (5ms)
```

### Custom Cache Key

```python
from backend.cache_config import cached

@cached(key_prefix="leaderboard", ttl=60)
def get_leaderboard(team_id, limit=10):
    # Cache key will be: "leaderboard:{team_id}:{json_of_kwargs}"
    # ...
    pass

# Different team_ids = different cache entries
leaderboard1 = get_leaderboard(1)  # team_id=1
leaderboard2 = get_leaderboard(2)  # team_id=2 (separate cache)
```

---

## CloudWatch Metrics Integration

### Report Query Performance

```python
from backend.cloudwatch_metrics import report_query_performance
import time

@some_bp.route("/api/expensive-query")
def expensive_query():
    start = time.time()
    
    # Your query
    result = db.session.query(SomeTable).filter(...).all()
    
    elapsed_ms = (time.time() - start) * 1000
    from_cache = False  # Set to True if served from cache
    
    # Report to CloudWatch
    report_query_performance("expensive_query", elapsed_ms, from_cache)
    
    return jsonify(result), 200
```

### Report API Metrics

```python
from backend.cloudwatch_metrics import report_api_call
import time

@some_bp.before_request
def track_request_start():
    from flask import g
    g.start_time = time.time()

@some_bp.after_request
def track_request_end(response):
    from flask import g, request
    
    elapsed_ms = (time.time() - g.start_time) * 1000
    
    # Report to CloudWatch
    report_api_call(
        endpoint=request.path,
        method=request.method,
        status_code=response.status_code,
        latency_ms=elapsed_ms
    )
    
    return response
```

### Report Application Errors

```python
from backend.cloudwatch_metrics import report_error

@some_bp.route("/api/something")
def do_something():
    try:
        # Your logic
        pass
    except Exception as e:
        report_error(
            error_type=type(e).__name__,
            endpoint=request.path
        )
        return jsonify({"error": str(e)}), 500
```

---

## Cache Invalidation Patterns

### Pattern 1: Invalidate on Update

```python
@admin_bp.route("/api/user/<int:user_id>", methods=["PUT"])
def update_user(user_id: int):
    data = request.get_json()
    
    # Update user
    user = User.query.get(user_id)
    user.display_name = data.get("display_name")
    db.session.commit()
    
    # Invalidate cache
    from backend.cached_queries import CachedQueries
    CachedQueries.invalidate_user_cache(user_id)
    
    return jsonify(user.to_dict()), 200
```

### Pattern 2: Invalidate on Delete

```python
@admin_bp.route("/api/team/<int:team_id>", methods=["DELETE"])
def delete_team(team_id: int):
    team = Team.query.get(team_id)
    db.session.delete(team)
    db.session.commit()
    
    # Invalidate all team cache entries
    from backend.cached_queries import CachedQueries
    CachedQueries.invalidate_team_cache(team_id)
    
    return jsonify({"deleted": True}), 200
```

### Pattern 3: Cascade Invalidation

```python
@admin_bp.route("/api/user/<int:user_id>/team", methods=["POST"])
def assign_user_to_team(user_id: int):
    data = request.get_json()
    team_id = data.get("team_id")
    
    # Create membership
    membership = Membership(user_id=user_id, team_id=team_id, active=True)
    db.session.add(membership)
    db.session.commit()
    
    # Invalidate all related caches
    from backend.cached_queries import CachedQueries
    CachedQueries.invalidate_user_cache(user_id)        # User's team list changed
    CachedQueries.invalidate_team_cache(team_id)        # Team membership changed
    CachedQueries.invalidate_dashboard_cache(user_id)   # User's dashboard data
    
    return jsonify({"status": "assigned"}), 200
```

---

## Metrics Collection

### Collect Metrics Manually

```python
from backend.monitoring import collect_and_report_metrics
from flask import current_app

@some_bp.route("/admin/metrics", methods=["POST"])
def collect_metrics():
    """Endpoint to manually trigger metrics collection."""
    success = collect_and_report_metrics(current_app)
    return jsonify({
        "status": "success" if success else "error"
    }), 200 if success else 500
```

### Get Current Pool Stats

```python
from backend.monitoring import get_pool_stats, get_cache_stats_dict
from flask import current_app

@some_bp.route("/admin/health", methods=["GET"])
def health_check():
    """Return system health metrics."""
    pool_stats = get_pool_stats(current_app)
    cache_stats = get_cache_stats_dict(current_app)
    
    return jsonify({
        "database": pool_stats,
        "cache": cache_stats,
        "timestamp": datetime.utcnow().isoformat()
    }), 200
```

---

## Performance Testing

### Before Cache

```bash
time curl http://localhost:5000/api/user/1
# real    0m0.150s
# user    0m0.050s
# sys     0m0.020s
```

### After Cache (First Request)

```bash
time curl http://localhost:5000/api/user/1
# real    0m0.160s  (slightly slower due to cache storage)
# user    0m0.050s
# sys     0m0.020s
```

### After Cache (Subsequent Requests)

```bash
time curl http://localhost:5000/api/user/1
# real    0m0.008s  (20x faster!)
# user    0m0.005s
# sys     0m0.001s
```

---

## Best Practices

### DO ✅

- Cache frequently accessed, infrequently updated data (users, teams, config)
- Use TTL appropriately (1min dashboard, 5min users, 15min teams)
- Invalidate cache when underlying data changes
- Monitor cache hit rates and adjust TTLs
- Fall back gracefully if Redis is unavailable
- Use composite cache keys for multi-parameter queries

### DON'T ❌

- Cache sensitive data (passwords, tokens, API keys)
- Use very long TTLs for frequently changing data (real-time metrics)
- Forget to invalidate cache when updating data
- Cache without monitoring hit rates
- Assume Redis will always be available in production (use fallback)
- Cache the same data with different keys (use consistent key naming)

---

## Debugging Cache Issues

### Check If Cache Is Working

```python
from backend.cache_config import cache_get, cache_set

# Store something
cache_set("test-key", {"data": "value"}, ttl=60)

# Retrieve it
result = cache_get("test-key")
print(result)  # Should print: {'data': 'value'}
```

### Monitor Cache Activity

```bash
# Terminal 1: Watch Redis commands
redis-cli MONITOR

# Terminal 2: Make API requests
curl http://localhost:5000/api/user/1
curl http://localhost:5000/api/user/1

# Terminal 1: Should show
# 1635200000.123456 [0 127.0.0.1:54321] "SETEX" "user:id:1" "300" "{...}"
# 1635200005.234567 [0 127.0.0.1:54321] "GET" "user:id:1"
```

### Check Cache Hit Rate

```bash
redis-cli INFO stats | grep keyspace
# Output:
# keyspace_hits:15234
# keyspace_misses:4107
# Hit rate: 15234 / (15234 + 4107) = 78.8%
```

### Clear Cache (if needed)

```bash
redis-cli FLUSHDB
# OK

# Or clear specific pattern
redis-cli KEYS "user:*" | xargs redis-cli DEL
```

---

## Examples by Blueprint

### Admin Blueprint

```python
from backend.cached_queries import CachedQueries

@admin_bp.route("/admin/dashboard")
def dashboard():
    user_id = session.get("_login_user_id")
    
    # Get user (cached 5 min)
    user = CachedQueries.get_user_by_id(db, user_id)
    
    # Get team hierarchy (cached 15 min)
    team_hierarchy = CachedQueries.get_team_hierarchy(db, user.active_team_id)
    
    return render_template("dashboard.html", user=user, teams=team_hierarchy)
```

### Tracker Blueprint

```python
from backend.cache_config import cache_set, cache_delete_pattern

@tracker_bp.route("/track", methods=["POST"])
def track():
    events = request.get_json().get("events", [])
    
    # Store telemetry events
    for event in events:
        telemetry = TelemetryEvent(**event)
        db.session.add(telemetry)
    db.session.commit()
    
    # Invalidate dashboard cache for this user
    user_id = events[0]["user_id"]
    cache_delete_pattern(f"dashboard:summary:{user_id}:*")
    
    return jsonify({"stored": len(events)}), 200
```

### Public Blueprint

```python
from backend.cached_queries import CachedQueries

@public_bp.route("/summary/today")
def summary_today():
    user_id = request.args.get("user_id")
    
    # Get cached summary (1 min TTL for dashboard)
    summary = CachedQueries.get_dashboard_summary(db, user_id, days=1)
    
    if summary is None:
        # Compute summary (expensive query)
        summary = _compute_summary(user_id)
    
    return jsonify(summary), 200
```

---

## Migration Checklist

When adding caching to an existing endpoint:

- [ ] Identify what data to cache (frequently accessed?)
- [ ] Choose appropriate TTL (1min, 5min, 15min?)
- [ ] Replace direct query with `CachedQueries` helper
- [ ] Add cache invalidation on create/update/delete
- [ ] Test that first request queries DB, second uses cache
- [ ] Monitor cache hit rate with `/metrics` endpoint
- [ ] Adjust TTL if needed based on hit rates
- [ ] Document the caching behavior in code comments

---

## Further Reading

- `DATABASE_OPTIMIZATION_GUIDE.md` — Comprehensive optimization documentation
- `CACHE_QUICKSTART.md` — Quick start guide for testing
- `backend/cache_config.py` — Cache configuration source
- `backend/cached_queries.py` — Cached query helper source
- `backend/cloudwatch_metrics.py` — CloudWatch integration source
