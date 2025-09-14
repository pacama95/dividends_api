# Gunicorn configuration for production deployment
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = 1  # Single worker for serverless - Cloud provider will scale horizontally
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True  # Improves memory usage and startup time

# Restart workers after this many requests, with up to 50 requests variation
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%h %l %u %t "%r" %s %b "%{Referer}i" "%{User-Agent}i" %D'

# Process naming
proc_name = 'dividend-api'

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# Performance
worker_tmp_dir = "/dev/shm"  # Use in-memory filesystem for better performance

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
