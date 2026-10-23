#!/usr/bin/env python
"""Repo-root Django entry so Render can run manage.py from /opt/render/project/src."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")
load_dotenv(ROOT / ".env")

if os.environ.get("RENDER"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    os.environ.setdefault("SECURE_SSL_REDIRECT", "false")
    if not os.environ.get("DJANGO_SECRET_KEY"):
        os.environ["DJANGO_SECRET_KEY"] = "render-build-placeholder-not-for-runtime"
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")


def _build_frontend() -> None:
    """Build the Ionic app so the API host can serve it at /."""
    import subprocess

    frontend = ROOT / "frontend"
    env = os.environ.copy()
    env.setdefault("FRONTEND_API_BASE_URL", "/api/v1")
    env.setdefault("FRONTEND_REALTIME_URL", "")
    env.setdefault("NODE_OPTIONS", "--max-old-space-size=2048")
    subprocess.run(["npm", "ci"], cwd=frontend, check=True, env=env)
    subprocess.run(["node", "scripts/write-render-env.mjs"], cwd=frontend, check=True, env=env)
    subprocess.run(["npm", "run", "build:prod"], cwd=frontend, check=True, env=env)


def main() -> None:
    if os.environ.get("RENDER") and sys.argv[1:2] == ["collectstatic"]:
        _build_frontend()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
