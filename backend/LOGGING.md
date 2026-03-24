# Centralized Logging System

## Overview

This project uses a **centralized enterprise-grade logging system** configured in `backend/logging_config.py`. All backend and tracker components use this single logging configuration for consistency.

## Features

- ✓ **Centralized configuration** - One place to configure all logging
- ✓ **Request context** - Automatically includes request ID, user ID, team ID in logs
- ✓ **Rotating file logs** - Prevents unlimited log growth (10 MB max, 5 backups)
- ✓ **Console + file output** - Development-friendly console, production-ready files
- ✓ **Environment-based** - Configure via `.env` (LOG_LEVEL, LOG_FILE, etc.)
- ✓ **Sensitive data filtering** - Automatically redacts passwords, tokens, secrets
- ✓ **Production-aware** - Works in demo mode, production mode, and tests
- ✓ **Easy to use** - Just `logger = logging.getLogger(__name__)`

## Quick Start

### Using the Logger in Any Module

```python
import logging

logger = logging.getLogger(__name__)

# Log at different levels
logger.debug("Detailed diagnostic information")
logger.info("Normal operation messages")
logger.warning("Something unexpected happened")
logger.error("An error occurred")
logger.critical("System failure")
```

### Log Levels

| Level | When to Use |
|---|---|
| `DEBUG` | Detailed diagnostic information (only in development) |
| `INFO` | General informational messages about normal operation |
| `WARNING` | Unexpected events or potential issues |
| `ERROR` | Errors that need attention but don't crash the app |
| `CRITICAL` | Severe errors that may cause app failure |

## Configuration

### Environment Variables (`.env`)

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log file path (rotating file handler)
LOG_FILE=logs/app.log

# Enable/disable file logging (console always enabled)
LOG_TO_FILE=true

# Max log file size before rotation (bytes, default 10 MB)
LOG_MAX_BYTES=10485760

# Number of backup log files to keep
LOG_BACKUP_COUNT=5
```

### Changing Log Level

**Development (verbose):**
```bash
LOG_LEVEL=DEBUG
```

**Production (normal):**
```bash
LOG_LEVEL=INFO
```

**Production (quiet):**
```bash
LOG_LEVEL=WARNING
```

## Log Format

### Console Output

```
2026-03-23 14:30:45 [INFO] backend.auth.authz [req:abc123 user:42 team:1]: Login successful
```

**Fields:**
- Timestamp (YYYY-MM-DD HH:MM:SS)
- Log level
- Logger name (module path)
- Request context (if inside Flask request)
  - `req:abc123` - Request ID (first 6 chars of UUID)
  - `user:42` - Current user ID
  - `team:1` - Current team ID
- Message

### File Output

Same format as console, written to `logs/app.log` with automatic rotation.

## Log Files

### Location

Default: `logs/app.log`

### Rotation

When `app.log` reaches 10 MB, it rotates:
```
logs/app.log         (current, up to 10 MB)
logs/app.log.1       (previous)
logs/app.log.2       (older)
logs/app.log.3
logs/app.log.4
logs/app.log.5       (oldest, deleted when new backup created)
```

### Reading Logs

**Tail live logs:**
```bash
tail -f logs/app.log
```

**Search for errors:**
```bash
grep ERROR logs/app.log
```

**Search across all rotated logs:**
```bash
grep -h "user:42" logs/app.log*
```

## Request Context

Logs automatically include Flask request context when available:

```python
from flask import g

# This happens automatically in middleware (request_context.py)
g.request_id = "abc123de-4567-89ab-cdef-0123456789ab"
g.current_user_id = 42
g.current_team_id = 1

# Your log statements automatically include context:
logger.info("User logged in")
# Output: 2026-03-23 14:30:45 [INFO] backend.auth [req:abc123 user:42 team:1]: User logged in
```

## Sensitive Data Protection

The logging system automatically **redacts sensitive data**:

| Pattern | Redacted As |
|---|---|
| `password=secret123` | `[REDACTED-PASSWORD]` |
| `token=xyz...` | `[REDACTED-TOKEN]` |
| `Bearer abc123...` | `Bearer [REDACTED-TOKEN]` |
| `secret=...` | `[REDACTED-SECRET]` |
| `api_key=...` | `[REDACTED-API-KEY]` |

**Important:** This is a safety net. **Avoid logging secrets in the first place.**

## What Gets Logged

### ✓ Logged

- Application startup/shutdown
- Authentication attempts (success/failure)
- Authorization denials
- Tracker ingestion summaries
- Database operation failures
- Validation errors
- Admin actions (via audit log)
- API errors
- Suspicious activity

### ✗ Not Logged

- Passwords
- Full tokens or API keys
- Session secrets
- Sensitive user content (unless explicitly needed for debugging)
- Excessive internal details (unless DEBUG level)

## Testing

### Disable Logging in Tests

Tests automatically use `LOG_LEVEL=WARNING` and `LOG_TO_FILE=false` (see `tests/conftest.py`).

To completely disable logging during tests:

```python
from backend.logging_config import disable_logging_for_tests, enable_logging_after_tests

def test_something():
    disable_logging_for_tests()
    # ... your test ...
    enable_logging_after_tests()
```

Or in pytest fixture:
```python
@pytest.fixture(autouse=True)
def silence_logs():
    disable_logging_for_tests()
    yield
    enable_logging_after_tests()
```

## Production Deployment

### Recommended Settings

```bash
LOG_LEVEL=INFO
LOG_FILE=/var/log/zinnia-axion/app.log
LOG_TO_FILE=true
LOG_MAX_BYTES=52428800  # 50 MB
LOG_BACKUP_COUNT=10
```

### Centralized Logging (ELK, Datadog, Loki)

The current setup logs to files. To send logs to external systems:

**Option 1: File-based (recommended)**
- Keep file logging enabled
- Use Filebeat, Fluentd, or Vector to ship logs to ELK/Datadog/Loki
- No code changes needed

**Option 2: Custom handler (advanced)**
- Add custom logging handler in `logging_config.py`
- Example: DatadogHandler, ElasticsearchHandler, etc.

## Examples

### Simple Logging

```python
import logging
logger = logging.getLogger(__name__)

def process_data(user_id):
    logger.info("Processing data for user %s", user_id)
    try:
        # ... process data ...
        logger.debug("Processed 100 records")
    except ValueError as e:
        logger.error("Data validation failed: %s", e)
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
```

### Logging with Context

```python
from flask import g

@app.route("/api/data")
def get_data():
    # Request context automatically included
    logger.info("Fetching data")  # [req:abc123 user:42] Fetching data
    return jsonify(data)
```

### Conditional Logging

```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("Expensive debug calculation: %s", compute_expensive_data())
```

### Exception Logging

```python
try:
    risky_operation()
except Exception as e:
    # Include full traceback
    logger.error("Operation failed", exc_info=True)
```

## Troubleshooting

### Logs not appearing

1. Check log level: `echo $LOG_LEVEL` (must be INFO or lower to see INFO logs)
2. Check file permissions: `ls -la logs/`
3. Check log file location: `echo $LOG_FILE`

### Logs too verbose

```bash
# Set higher log level
LOG_LEVEL=WARNING
```

### Logs too quiet

```bash
# Set lower log level
LOG_LEVEL=DEBUG
```

### Log file too large

```bash
# Reduce max file size
LOG_MAX_BYTES=5242880  # 5 MB

# Or increase backup count to keep more history
LOG_BACKUP_COUNT=20
```

### Want structured JSON logs

Add a JSON formatter in `logging_config.py`:

```python
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(g, "request_id", None),
        })
```

## Best Practices

### ✓ Do

- Use `logger.info()` for normal operations
- Use `logger.warning()` for unexpected but handled events
- Use `logger.error()` for errors that need attention
- Include context in messages: `logger.info("User %s logged in", user_id)`
- Use `exc_info=True` for exceptions: `logger.error("Failed", exc_info=True)`
- Log at module level: `logger = logging.getLogger(__name__)`

### ✗ Don't

- Don't use `print()` statements (they bypass logging config)
- Don't log secrets, tokens, or passwords
- Don't log at DEBUG level in production
- Don't construct expensive log messages eagerly: use `%s` placeholders
- Don't over-log: avoid logging every tiny internal step

## Architecture

### Components

```
backend/logging_config.py          ← Central logging configuration
backend/app.py                     ← Calls setup_logging() at startup
tracker/agent.py                   ← Calls setup_logging() for tracker
backend/middleware/request_context.py  ← Provides g.request_id
```

### Flow

```
Application Startup
    ↓
setup_logging()
    ↓
Configure root logger
    ↓
Add console handler (stdout)
    ↓
Add rotating file handler (logs/app.log)
    ↓
Add request context formatter
    ↓
Add sensitive data filter
    ↓
All modules use configured logger
```

## Migration Notes

### Before (Old Way)

```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")
```

### After (New Way)

```python
# In app.py/agent.py:
from backend.logging_config import setup_logging
setup_logging(app)

# In any module:
import logging
logger = logging.getLogger(__name__)
```

**No other changes needed** - existing logger calls still work!

---

For questions or issues with logging, see `backend/logging_config.py` or contact the development team.
