from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Login and register: 5 attempts per minute per IP."""

    scope = "auth"


class TryDemoRateThrottle(SimpleRateThrottle):
    """Landing demos: signed-in users share one bucket; guests are limited per IP."""

    scope = "try_demo"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ClientErrorThrottle(SimpleRateThrottle):
    """Error reports from browsers and phones: per signed-in user, else per IP."""

    scope = "client_errors"

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user and request.user.is_authenticated else None
        return self.cache_format % {"scope": self.scope, "ident": ident or self.get_ident(request)}
