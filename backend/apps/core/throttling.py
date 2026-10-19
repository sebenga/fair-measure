"""Rate limits that stay out of the way when Redis is down.

Login and registration are the endpoints worth slowing down. The default cache
is Redis, and a cache outage must not turn sign-in into an error: the rest of
the API already treats Redis as best-effort.
"""

from __future__ import annotations

import logging

from rest_framework.throttling import AnonRateThrottle

logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"

    def allow_request(self, request, view) -> bool:
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning("Skipped the auth rate limit because the cache is unavailable.")
            return True
