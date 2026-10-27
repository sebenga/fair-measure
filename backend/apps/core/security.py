"""Browser security headers that Django does not set on its own."""

from __future__ import annotations

from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if "Content-Security-Policy" not in response:
            # Pages that already injected a nonce keep theirs. APIs get a tight default.
            policy = getattr(settings, "CONTENT_SECURITY_POLICY", "")
            if policy:
                response["Content-Security-Policy"] = policy.format(nonce="unused")
        return response
