from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Login and register: 5 attempts per minute per IP."""

    scope = "auth"
