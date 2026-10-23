"""Let `gunicorn config.wsgi:application` work when cwd is the repo root."""

import os
import sys
from pathlib import Path

backend = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend))
chdir = str(backend)
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 1
threads = 4
timeout = 120
wsgi_app = "config.wsgi:application"
