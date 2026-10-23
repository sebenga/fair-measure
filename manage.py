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


def main() -> None:
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
