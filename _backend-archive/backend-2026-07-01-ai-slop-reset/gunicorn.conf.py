# =============================================================================
# Owlbell — Gunicorn Production WSGI Server Configuration
# =============================================================================
# This file configures Gunicorn for serving the FastAPI application
# in production environments.
#
# Usage:
#   gunicorn -c backend/gunicorn.conf.py main:app
#
# Or with the Makefile:
#   make deploy
#
# References:
#   https://docs.gunicorn.org/en/stable/configure.html
#   https://docs.gunicorn.org/en/stable/settings.html
# =============================================================================

import multiprocessing
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Server socket binding
# ---------------------------------------------------------------------------

# Bind to all interfaces on port 8000 (inside container)
# Nginx or a load balancer will forward traffic here.
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Number of seconds to wait for requests on a Keep-Alive connection.
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "120"))

# Maximum number of simultaneous clients per worker.
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))

# The maximum size of HTTP request line in bytes.
limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", "8190"))

# Limit the number of HTTP headers fields in a request.
limit_request_fields = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELDS", "200"))

# Limit the allowed size of an HTTP request header field.
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", "16380"))

# ---------------------------------------------------------------------------
# Worker processes
# ---------------------------------------------------------------------------

# Formula: CPU cores * 2 + 1 (good default for I/O-bound applications)
default_workers = multiprocessing.cpu_count() * 2 + 1
workers = int(os.getenv("GUNICORN_WORKERS", str(default_workers)))

# Worker class — Uvicorn for ASGI (FastAPI)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")

# Threads per worker (for sync workers only; ignored by UvicornWorker)
threads = int(os.getenv("GUNICORN_THREADS", "1"))

# The type of workers to use (sync, gthread, eventlet, gevent, tornado)
# UvicornWorker handles async natively, so we use sync here as the base.
# worker_class already specifies UvicornWorker above.

# Maximum requests a worker will process before restarting (prevents memory leaks)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "10000"))

# Jitter to add to max_requests (prevents all workers restarting at once)
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "1000"))

# Worker timeout in seconds
# Should be longer than the longest expected request (e.g., LLM calls)
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Graceful timeout — workers have this many seconds to finish handling
# requests after receiving a restart signal.
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# Server mechanics
# ---------------------------------------------------------------------------

# Run Gunicorn as a daemon (not recommended inside Docker — let PID 1 handle it)
daemon = os.getenv("GUNICORN_DAEMON", "false").lower() == "true"

# Write the process ID to a file
pidfile = os.getenv("GUNICORN_PIDFILE", "/tmp/gunicorn.pid")

# Directory to change to before loading workers
chdir = str(Path(__file__).resolve().parent)

# Store the HTTP request/response in a temporary file if larger than this.
# proxy_buffering off in Nginx makes this less critical.
tmp_upload_dir = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Log level: debug, info, warning, error, critical
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Access log file ("-" for stdout)
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")

# Error log file ("-" for stderr)
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")

# Access log format
# Parameters: http://docs.gunicorn.org/en/stable/settings.html#access-log-format
access_log_format = os.getenv(
    "GUNICORN_ACCESS_LOG_FORMAT",
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
)

# Whether to send output to syslog
syslog = os.getenv("GUNICORN_SYSLOG", "false").lower() == "true"
syslog_addr = os.getenv("GUNICORN_SYSLOG_ADDR", "udp://localhost:514")

# Disable redirect stdout/stderr to log file (keep them for container logging)
capture_output = os.getenv("GUNICORN_CAPTURE_OUTPUT", "true").lower() == "true"

# Preload the application before forking workers
# Saves memory with copy-on-write but can cause issues with some libraries.
preload_app = os.getenv("GUNICORN_PRELOAD", "false").lower() == "true"

# ---------------------------------------------------------------------------
# SSL / Security
# ---------------------------------------------------------------------------

# SSL key file (handled by Nginx in production)
keyfile = os.getenv("GUNICORN_SSL_KEY", "")

# SSL certificate file
# certfile = os.getenv("GUNICORN_SSL_CERT", "")

# SSL version
cert_reqs = int(os.getenv("GUNICORN_SSL_CERT_REQS", "0"))

# ---------------------------------------------------------------------------
# Process naming
# ---------------------------------------------------------------------------

# Process name shown in ps/top
proc_name = os.getenv("GUNICORN_PROC_NAME", "answerflow-api")

# Append the process ID to the process name
default_proc_name = "answerflow-api"

# ---------------------------------------------------------------------------
# Server hooks (optional instrumentation)
# ---------------------------------------------------------------------------


def on_starting(server):
    """Called just before the master process is initialized."""
    pass


def on_reload(server):
    """Called when receiving SIGHUP signal."""
    pass


def when_ready(server):
    """Called just after the server is started."""
    pass


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass


def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    pass


def worker_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    pass


def on_exit(server):
    """Called just before exiting Gunicorn."""
    pass
