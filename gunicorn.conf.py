# gunicorn.conf.py
import multiprocessing
import os

# Worker settings - reduce memory usage
bind = "0.0.0.0:8000"
workers = 2  # Reduced from default (cpu_count * 2 + 1)
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Memory optimization
max_requests = 1000
max_requests_jitter = 100

# Preload app to save memory
preload_app = True

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Graceful timeout
graceful_timeout = 30

# Worker temporary directory
worker_tmp_dir = "/dev/shm"

# Memory limit (in MB)
# worker_max_memory = 200  # Uncomment if needed

# Environment
raw_env = [
    'DJANGO_SETTINGS_MODULE=winda.settings_production',
]