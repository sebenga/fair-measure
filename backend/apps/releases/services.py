"""Release switches: what the public can see, and who may change it."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

CACHE_KEY = "releases:state:v1"

# Modules the platform admin can open or close. Scouting covers the scout-facing
# tools only: a player's own profile and team invites stay available.
FEATURES: list[dict] = [
    {
        "key": "games",
        "label": "Multi-sport Games",
        "description": "Olympic-style Games with events, nations, athletes and medal tables.",
        "default": True,
    },
    {
        "key": "scouting",
        "label": "Scouting",
        "description": "Talent search, shortlists, ratings, tests, scout reports, league squads.",
        "default": True,
    },
    {
        "key": "fantasy",
        "label": "Fantasy",
        "description": "Fantasy squads and performance points inside leagues.",
        "default": True,
    },
    {
        "key": "discover",
        "label": "Discover",
        "description": "The Discover tab: feed, partners and featured competitions.",
        "default": True,
    },
    {
        "key": "partnerships",
        "label": "Partnerships",
        "description": "The corporate and government partnerships page.",
        "default": True,
    },
    {
        "key": "horses",
        "label": "Horse register",
        "description": "The My horses page. Equestrian entries can still look horses up.",
        "default": False,
    },
]
FEATURE_DEFAULTS = {row["key"]: row["default"] for row in FEATURES}


def _state() -> dict[str, dict[str, bool]]:
    ttl = getattr(settings, "RELEASES_CACHE_SECONDS", 15)
    if ttl:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached
    from .models import Release

    state: dict[str, dict[str, bool]] = {"sport": {}, "feature": {}}
    for kind, key, live in Release.objects.values_list("kind", "key", "live"):
        state.setdefault(kind, {})[key] = live
    if ttl:
        cache.set(CACHE_KEY, state, ttl)
    return state


def forget() -> None:
    cache.delete(CACHE_KEY)


def is_platform_admin(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    emails = {email.strip().lower() for email in settings.PLATFORM_ADMIN_EMAILS if email.strip()}
    return (user.email or "").lower() in emails


def sport_is_live(key: str) -> bool:
    explicit = _state()["sport"].get(key)
    if explicit is not None:
        return explicit
    from apps.competitions.presets import PRESETS

    preset = PRESETS.get(key)
    # KPI, cleaning and custom are the core product, not a sport to roll out.
    if preset is not None and preset.get("kind", "sport") != "sport":
        return True
    return bool(settings.RELEASES_SPORTS_LIVE_BY_DEFAULT)


def hidden_sports() -> list[str]:
    from apps.competitions.presets import PRESETS

    return [key for key in PRESETS if not sport_is_live(key)]


def feature_is_live(key: str) -> bool:
    explicit = _state()["feature"].get(key)
    if explicit is not None:
        return explicit
    return FEATURE_DEFAULTS.get(key, True)


def feature_map() -> dict[str, bool]:
    return {row["key"]: feature_is_live(row["key"]) for row in FEATURES}


def set_live(kind: str, keys: list[str], live: bool, user=None) -> int:
    from .models import Release

    changed = 0
    for key in keys:
        Release.objects.update_or_create(
            kind=kind, key=key, defaults={"live": live, "updated_by": user}
        )
        changed += 1
    forget()
    return changed
