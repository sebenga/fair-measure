"""Sample values that make seeded and demo players scout-eligible.

Scouts only see complete profiles (see `services.scout_readiness`). Demo leagues,
seed commands and tests use this to fill whatever is still empty. Real people
fill their own profiles; nothing here runs for them. Date of birth is left to the
caller because age decides consent.
"""

from __future__ import annotations

from .models import PlayerProfile, PlayerSport

# The account fields `scout_readiness` checks, in the order sample values fill them.
SAMPLE_ACCOUNT_FIELDS = (
    "display_name",
    "given_name",
    "family_name",
    "bio",
    "avatar_url",
    "id_number",
    "phone",
    "city",
    "country",
)


def sample_account_details(
    user, *, sport: str = "soccer", given: str = "", family: str = ""
) -> list[str]:
    """Set sample values on the account fields that are still empty. Nothing is saved;
    the caller writes the returned fields (singly or in bulk)."""

    given = given or user.given_name or (user.display_name or "").split(" ")[0]
    family = family or user.family_name
    name = " ".join(part for part in (given, family) if part) or "Player"
    account = {
        "display_name": name,
        "given_name": given or name.split()[0],
        "family_name": family or "Player",
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
    changed = [
        field for field in SAMPLE_ACCOUNT_FIELDS if not str(getattr(user, field) or "").strip()
    ]
    for field in changed:
        setattr(user, field, account[field])
    return changed


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
    changed = sample_account_details(
        user, sport=sport, given=profile.first_name, family=profile.last_name
    )
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
