"""Sample values that make seeded and demo players scout-eligible.

Scouts only see complete profiles (see `services.scout_readiness`). Demo leagues,
seed commands and tests use this to fill whatever is still empty. Real people
fill their own profiles; nothing here runs for them. Date of birth is left to the
caller because age decides consent.
"""

from __future__ import annotations

from .models import PlayerProfile, PlayerSport


def fill_sample_profile(
    profile: PlayerProfile,
    *,
    sport: str = "soccer",
    position: str = "central-midfield",
    region: str = "gauteng",
    gender: str = "men",
    club: str = "Sample FC",
) -> PlayerProfile:
    user = profile.user
    name = " ".join(part for part in (profile.first_name, profile.last_name) if part) or "Player"
    account = {
        "display_name": name,
        "given_name": profile.first_name or name.split()[0],
        "family_name": profile.last_name or "Player",
        "bio": f"{name} plays {sport} on Fair Measure.",
        "avatar_url": (
            f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}"
            "&background=0f766e&color=fff"
        ),
        "id_number": f"SAMPLE-{str(user.pk)[:8].upper()}",
        "phone": "+27 10 000 0000",
        "city": "Johannesburg",
        "country": "South Africa",
    }
    changed = [field for field in account if not str(getattr(user, field) or "").strip()]
    for field in changed:
        setattr(user, field, account[field])
    if changed:
        user.save(update_fields=[*changed, "updated_at"])

    scouting = {"gender_category": gender, "region": region}
    if not profile.school_or_club and not profile.teams.exists():
        scouting["school_or_club"] = club
    filled = [field for field, value in scouting.items() if not getattr(profile, field)]
    for field in filled:
        setattr(profile, field, scouting[field])
    if not profile.photo_url:
        profile.photo_url = user.avatar_url
        filled.append("photo_url")
    if not profile.bio:
        profile.bio = user.bio
        filled.append("bio")
    if filled:
        profile.save(update_fields=[*filled, "updated_at"])

    sports = list(profile.sports.all())
    if not any(row.primary_position for row in sports):
        row = next((item for item in sports if item.sport == sport), None)
        if row is None:
            PlayerSport.objects.create(
                profile=profile,
                sport=sport,
                primary_position=position,
                is_primary=not any(item.is_primary for item in sports),
            )
        else:
            row.primary_position = position
            row.save(update_fields=["primary_position", "updated_at"])
    return profile
