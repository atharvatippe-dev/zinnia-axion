"""
Gunicorn production configuration for Zinnia Axion backend.
"""
import multiprocessing
import os

# ── Server Socket ──────────────────────────────────────
bind = f"{os.getenv('FLASK_HOST', '0.0.0.0')}:{os.getenv('FLASK_PORT', '5000')}"
backlog = 2048  # Pending connections queue

# ── Worker Processes ───────────────────────────────────
# Formula: (2 × CPU cores) + 1
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'  # Sync workers (best for Flask + PostgreSQL)
worker_connections = 1000  # Max simultaneous clients per worker
max_requests = 1000  # Restart worker after 1000 requests (prevent memory leaks)
max_requests_jitter = 50  # Add randomness to avoid all workers restarting simultaneously
timeout = 30  # Worker timeout (30s for /track endpoint batches)
graceful_timeout = 30  # Time to finish current requests on shutdown
keepalive = 5  # Keep-alive for client connections

# ── Logging ────────────────────────────────────────────
accesslog = '-'  # Log to stdout (CloudWatch picks it up)
errorlog = '-'   # Log to stderr
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# ── Process Naming ─────────────────────────────────────
proc_name = 'zinnia-axion-backend'

# ── Server Mechanics ───────────────────────────────────
daemon = False  # Run in foreground (required for Docker/ECS)
pidfile = None  # Don't create PID file in containerized environments
umask = 0
user = None
group = None
tmp_upload_dir = None

# ── Server Hooks ───────────────────────────────────────
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Gunicorn server")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Gunicorn workers")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info(f"Gunicorn ready. Workers: {workers}, Bind: {bind}")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(f"Worker exited (pid: {worker.pid})")
