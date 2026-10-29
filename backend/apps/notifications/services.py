"""Firebase Cloud Messaging delivery.

Firebase is initialised lazily and treated as optional: with no credentials the
functions record the in-app notification and skip the push, so local development
and tests never need a Firebase project.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from django.conf import settings

from apps.core.apps import fit_char_fields

from .models import DeviceToken, Notification, NotificationPreference

logger = logging.getLogger(__name__)

# FCM error codes that mean the token will never work again, as opposed to a
# transient failure worth retrying.
DEAD_TOKEN_CODES = {"NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT"}

_firebase_app = None
_firebase_unavailable = False


def _get_firebase_app():
    global _firebase_app, _firebase_unavailable
    if _firebase_app is not None or _firebase_unavailable:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning("firebase-admin is not installed; push notifications disabled.")
        _firebase_unavailable = True
        return None

    try:
        if settings.FIREBASE_CREDENTIALS_JSON:
            cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
        elif settings.FIREBASE_CREDENTIALS_FILE:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
        else:
            logger.info("No Firebase credentials configured; push notifications disabled.")
            _firebase_unavailable = True
            return None

        options = (
            {"projectId": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else None
        )
        _firebase_app = firebase_admin.initialize_app(cred, options)
    except Exception as exc:
        logger.error("Could not initialise Firebase: %s", exc)
        _firebase_unavailable = True
        return None

    return _firebase_app


def wants_notification(user, competition, category: str) -> bool:
    """Competition-specific preferences win; otherwise fall back to the global row."""

    preference = (
        NotificationPreference.objects.filter(user=user, competition=competition).first()
        or NotificationPreference.objects.filter(user=user, competition__isnull=True).first()
    )
    if preference is None:
        return True
    return getattr(preference, category, True)


def send_push(
    tokens: Iterable[str], title: str, body: str, data: dict | None = None
) -> int:
    """Send to many devices. Returns the number of successful deliveries."""

    token_list = [token for token in tokens if token]
    if not token_list:
        return 0

    app = _get_firebase_app()
    if app is None:
        logger.info("Push suppressed (Firebase not configured): %s", title)
        return 0

    from firebase_admin import messaging

    message = messaging.MulticastMessage(
        tokens=token_list,
        notification=messaging.Notification(title=title, body=body),
        # FCM data values must all be strings.
        data={key: str(value) for key, value in (data or {}).items()},
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
        ),
    )

    try:
        response = messaging.send_each_for_multicast(message)
    except Exception as exc:
        logger.error("FCM send failed: %s", exc)
        return 0

    # Prune tokens the device has invalidated so we stop paying to retry them.
    dead_tokens = [
        token_list[index]
        for index, result in enumerate(response.responses)
        if not result.success
        and getattr(result.exception, "code", "") in DEAD_TOKEN_CODES
    ]
    if dead_tokens:
        DeviceToken.objects.filter(token__in=dead_tokens).update(is_active=False)

    return response.success_count


def notify_users(
    users,
    *,
    kind: str,
    title: str,
    body: str = "",
    competition=None,
    category: str = "feed_activity",
    data: dict | None = None,
) -> int:
    """Record an in-app notification and push it to every opted-in device."""

    recipients = [user for user in users if wants_notification(user, competition, category)]
    if not recipients:
        return 0

    rows = [
        Notification(
            user=user,
            competition=competition,
            kind=kind,
            title=title,
            body=body,
            data=data or {},
        )
        for user in recipients
    ]
    # bulk_create skips pre_save, and titles embed competition names.
    for row in rows:
        fit_char_fields(row)
    Notification.objects.bulk_create(rows)

    tokens = DeviceToken.objects.filter(
        user__in=recipients, is_active=True
    ).values_list("token", flat=True)

    return send_push(tokens, title, body, {**(data or {}), "kind": kind})
