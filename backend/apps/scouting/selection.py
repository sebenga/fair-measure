"""League squads: rank a competition's players and pick a national-team style squad.

Every number comes from stored data (match ratings, player-tagged score events
and team results). Nothing is estimated: a player with no evidence has no score,
and each pick records which sources it was based on. Squad shapes come from the
catalogue, so nothing here names a sport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from . import catalog
from .models import LeagueSquad, PlayerProfile, SquadPick
from .services import account_name, effective_visibility, ensure_player_profile

TEN = Decimal("10")
OTHER_GROUP = {"key": "other", "label": "Position not set", "positions": [], "min": 0}


@dataclass
class Candidate:
    user_id: object
    name: str
    roster_member_id: object
    team_id: object
    team_name: str
    profile: PlayerProfile
    position_label: str
    group_key: str | None
    group_keys: list[str]
    available: bool
    availability: str
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    ratings: list[Decimal] = field(default_factory=list)
    points: Decimal = Decimal("0")
    components: dict[str, Decimal] = field(default_factory=dict)
    score: Decimal | None = None

    @property
    def avg_rating(self) -> Decimal | None:
        if not self.ratings:
            return None
        return sum(self.ratings, Decimal("0")) / len(self.ratings)

    @property
    def confidence(self) -> str:
        if len(self.ratings) >= 3:
            return "strong"
        if self.ratings or self.points > 0:
            return "some"
        if self.games:
            return "thin"
        return "none"

    def evidence(self) -> dict:
        lines: list[str] = []
        if self.ratings:
            lines.append(
                f"Average match rating {_fmt(self.avg_rating)} from {len(self.ratings)} "
                f"{'game' if len(self.ratings) == 1 else 'games'}"
            )
        if self.points > 0:
            per_game = self.points / self.games if self.games else None
            lines.append(
                f"{_fmt(self.points)} points scored"
                + (f" ({_fmt(per_game)} per game)" if per_game is not None else "")
            )
        if self.games:
            lines.append(f"Team record W{self.wins} D{self.draws} L{self.losses}")
        return {
            "basis": sorted(self.components),
            "components": {key: _fmt(value) for key, value in self.components.items()},
            "ratings": len(self.ratings),
            "avg_rating": _fmt(self.avg_rating) if self.ratings else None,
            "points": _fmt(self.points),
            "games": self.games,
            "record": {"won": self.wins, "drawn": self.draws, "lost": self.losses},
            "confidence": self.confidence,
            "summary": lines or ["No match data recorded for this player yet"],
        }


def _fmt(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f")


def league_sport(competition) -> str | None:
    return catalog.sport_for_competition(competition.sport)


def template_for(competition) -> dict:
    return catalog.squad_template(league_sport(competition))


def _groups_of(candidate: Candidate) -> list[str]:
    if candidate.group_keys:
        return candidate.group_keys
    return [candidate.group_key] if candidate.group_key else []


def _position_of(profile: PlayerProfile, roster_position: str, sport_key: str | None):
    """Where the player is picked: the team's roster decides, the profile adds detail.

    The roster position is set by the team, so it wins when it maps to a squad group.
    The profile's finer position (say "Centre-back") is used as the label when it
    agrees, and decides on its own only when the roster gives no usable position.
    """

    labels = {
        item["key"]: item["label"]
        for item in (catalog.sport(sport_key or "") or {}).get("positions", [])
    }
    declared = next(
        (
            sport.primary_position
            for sport in profile.sports.all()
            if sport_key and sport.sport == sport_key and sport.primary_position
        ),
        "",
    )
    declared_group = catalog.group_for_position(sport_key, declared) if declared else None
    roster_group = catalog.group_for_position(sport_key, roster_position)

    if roster_group is not None:
        label = (
            labels.get(declared, declared) if declared_group == roster_group else roster_position
        )
        return label, roster_group
    if declared_group is not None:
        return labels.get(declared, declared), declared_group
    return roster_position, None


def _positions_played(profile: PlayerProfile, member, sport_key: str | None, labels: list[str]):
    """Match shirts first; the roster and profile are only a fallback."""

    groups: list[str] = []
    shown: list[str] = []
    catalog_labels = {
        item["key"]: item["label"]
        for item in (catalog.sport(sport_key or "") or {}).get("positions", [])
    }
    for label in labels:
        group = catalog.group_for_position(sport_key, label)
        if group and group not in groups:
            groups.append(group)
        text = catalog_labels.get(label, label)
        if text and text not in shown:
            shown.append(text)
    if groups:
        return " · ".join(shown), groups, groups[0]
    fallback_label, fallback_group = _position_of(profile, member.position, sport_key)
    return fallback_label, [fallback_group] if fallback_group else [], fallback_group


def candidates(competition) -> tuple[list[Candidate], dict]:
    """Every player in the league who has opted in to scouting, ranked.

    Rostered players are taken from their account. Private visibility
    (including under-18s still waiting for a guardian) is only counted,
    never listed.
    """

    from apps.competitions.models import RosterMember
    from apps.fixtures.models import Fixture, FixtureSide, PlayerMatchRating, ScoreEvent
    from apps.fixtures.played import lineup_positions

    sport_key = league_sport(competition)
    roster = list(
        RosterMember.objects.filter(
            participant__competition=competition,
            participant__kind="team",
            participant__is_active=True,
            is_active=True,
            user__isnull=False,
        )
        .select_related("participant", "user")
        .order_by("participant__name", "name")
    )
    user_ids = {member.user_id for member in roster}
    profiles = {
        profile.user_id: profile
        for profile in PlayerProfile.objects.filter(user_id__in=user_ids).prefetch_related("sports")
    }

    finished = [Fixture.Status.COMPLETED, Fixture.Status.FORFEIT]
    records: dict[object, dict[str, int]] = {}
    for side in FixtureSide.objects.filter(
        fixture__competition=competition, fixture__status__in=finished
    ).values("participant_id", "outcome"):
        record = records.setdefault(side["participant_id"], {"win": 0, "draw": 0, "loss": 0})
        if side["outcome"] in record:
            record[side["outcome"]] += 1

    ratings: dict[object, list[Decimal]] = {}
    for row in PlayerMatchRating.objects.filter(
        fixture__competition=competition, player__user_id__in=user_ids
    ).values("player__user_id", "rating"):
        ratings.setdefault(row["player__user_id"], []).append(row["rating"])

    points: dict[object, Decimal] = {}
    for row in ScoreEvent.objects.filter(
        fixture__competition=competition,
        player__user_id__in=user_ids,
        scoring_category__affects_score=True,
    ).values("player__user_id", "quantity", "scoring_category__points"):
        uid = row["player__user_id"]
        points[uid] = (
            points.get(uid, Decimal("0")) + row["quantity"] * row["scoring_category__points"]
        )

    played_shirts = lineup_positions(competition, {member.id for member in roster})
    counts = {"rostered": len(user_ids), "no_profile": 0, "private": 0, "eligible": 0}
    chosen: dict[object, Candidate] = {}
    for member in roster:
        if member.user_id in chosen:
            continue
        profile = profiles.get(member.user_id)
        if profile is None and member.user_id:
            profile = ensure_player_profile(member.user)
            profiles[member.user_id] = profile
        if profile is None:
            continue
        if effective_visibility(profile) == PlayerProfile.Visibility.PRIVATE:
            continue
        record = records.get(member.participant_id, {"win": 0, "draw": 0, "loss": 0})
        shirts = played_shirts.get(member.id, [])
        label, groups, group = _positions_played(profile, member, sport_key, shirts)
        given, family = account_name(member.user)
        chosen[member.user_id] = Candidate(
            user_id=member.user_id,
            name=" ".join(part for part in (given, family) if part)
            or profile.full_name
            or member.name,
            roster_member_id=member.id,
            team_id=member.participant_id,
            team_name=member.participant.name,
            profile=profile,
            position_label=label or "",
            group_key=group,
            group_keys=groups,
            available=profile.availability not in catalog.UNAVAILABLE_FOR_SELECTION,
            availability=profile.availability,
            games=sum(record.values()),
            wins=record["win"],
            draws=record["draw"],
            losses=record["loss"],
            ratings=ratings.get(member.user_id, []),
            points=points.get(member.user_id, Decimal("0")),
        )
    for uid in user_ids:
        profile = profiles.get(uid)
        if profile is None:
            counts["no_profile"] += 1
        elif uid not in chosen:
            counts["private"] += 1
    counts["eligible"] = len(chosen)

    _score(list(chosen.values()))
    ranked = sorted(chosen.values(), key=_rank_key)
    return ranked, counts


def _score(pool: list[Candidate]) -> None:
    # Output is ranked against the same position group: defenders are not marked
    # down for scoring less than strikers.
    per_game = {
        candidate.user_id: candidate.points / candidate.games
        for candidate in pool
        if candidate.games and candidate.points > 0
    }
    best: dict[str | None, Decimal] = {}
    for candidate in pool:
        value = per_game.get(candidate.user_id)
        if value is not None and value > best.get(candidate.group_key, Decimal("0")):
            best[candidate.group_key] = value
    for candidate in pool:
        if candidate.ratings:
            candidate.components["form"] = min(candidate.avg_rating, TEN)
        group_best = best.get(candidate.group_key, Decimal("0"))
        if group_best > 0 and candidate.games:
            candidate.components["output"] = (
                TEN * per_game.get(candidate.user_id, Decimal("0")) / group_best
            )
        if candidate.games:
            candidate.components["team"] = (
                TEN * (Decimal(candidate.wins) + Decimal(candidate.draws) / 2) / candidate.games
            )
        weights = {
            key: Decimal(str(catalog.SELECTION_WEIGHTS[key]))
            for key in candidate.components
            if key in catalog.SELECTION_WEIGHTS
        }
        total = sum(weights.values(), Decimal("0"))
        if total:
            candidate.score = (
                sum(candidate.components[key] * weight for key, weight in weights.items()) / total
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rank_key(candidate: Candidate):
    return (
        candidate.score is None,
        -(candidate.score or Decimal("0")),
        -len(candidate.ratings),
        -candidate.games,
        candidate.name.lower(),
    )


def groups_of(template: dict) -> list[dict]:
    return [*template["groups"], OTHER_GROUP]


def squad_warnings(squad: LeagueSquad, template: dict, picks: list[SquadPick]) -> list[str]:
    warnings: list[str] = []
    by_group: dict[str, int] = {}
    for pick in picks:
        by_group[pick.group_key] = by_group.get(pick.group_key, 0) + 1
    for group in template["groups"]:
        have = by_group.get(group["key"], 0)
        if have < group["min"]:
            warnings.append(
                f"{group['label']}: {have} of the {group['min']} wanted. "
                "Not enough eligible players with that position."
            )
        elif have > group.get("max", squad.size):
            warnings.append(f"{group['label']}: {have} picked, more than the usual {group['max']}.")
    if len(picks) < squad.size:
        warnings.append(f"{len(picks)} of {squad.size} places filled.")
    unproven = sum(1 for pick in picks if pick.evidence.get("confidence") in {"thin", "none"})
    if unproven:
        warnings.append(
            f"{unproven} pick(s) rest on team results only. Add match ratings or tag "
            "scorers to sharpen the selection."
        )
    return warnings


def pick_from(
    candidate: Candidate, squad: LeagueSquad, group_key: str, *, locked: bool, order: int
):
    return SquadPick(
        squad=squad,
        user_id=candidate.user_id,
        roster_member_id=candidate.roster_member_id,
        group_key=group_key,
        position_label=candidate.position_label,
        score=candidate.score,
        evidence={**candidate.evidence(), "team": candidate.team_name},
        locked=locked,
        order=order,
    )


@transaction.atomic
def generate(squad: LeagueSquad, by=None) -> list[SquadPick]:
    """Fill the squad: keep locked picks, then group minimums, then the best of the rest."""

    template = template_for(squad.competition)
    pool, _ = candidates(squad.competition)
    by_user = {candidate.user_id: candidate for candidate in pool}
    excluded = {str(item) for item in squad.excluded_users}

    locked = list(squad.picks.filter(locked=True))
    squad.picks.filter(locked=False).delete()
    for pick in locked:
        # Refresh the evidence behind a hand-picked player without moving them.
        candidate = by_user.get(pick.user_id)
        if candidate is not None:
            pick.score = candidate.score
            pick.evidence = {**candidate.evidence(), "team": candidate.team_name}
            pick.position_label = candidate.position_label
            pick.save(update_fields=["score", "evidence", "position_label", "updated_at"])

    taken = {pick.user_id for pick in locked}
    counts: dict[str, int] = {}
    for pick in locked:
        counts[pick.group_key] = counts.get(pick.group_key, 0) + 1

    available = [
        candidate
        for candidate in pool
        if candidate.available
        and candidate.user_id not in taken
        and str(candidate.user_id) not in excluded
    ]
    chosen: list[tuple[Candidate, str]] = []
    room = max(squad.size - len(locked), 0)

    def take(candidate: Candidate, group_key: str) -> None:
        chosen.append((candidate, group_key))
        taken.add(candidate.user_id)
        counts[group_key] = counts.get(group_key, 0) + 1

    for group in template["groups"]:
        for candidate in available:
            if len(chosen) >= room or counts.get(group["key"], 0) >= group["min"]:
                break
            if candidate.user_id not in taken and group["key"] in _groups_of(candidate):
                take(candidate, group["key"])

    limits = {group["key"]: group.get("max", squad.size) for group in template["groups"]}
    for candidate in available:
        if len(chosen) >= room:
            break
        if candidate.user_id in taken:
            continue
        for key in _groups_of(candidate):
            if counts.get(key, 0) < limits.get(key, squad.size):
                take(candidate, key)
                break

    # Still short: players whose position is not set, so the squad is never left empty.
    for candidate in available:
        if len(chosen) >= room:
            break
        if candidate.user_id not in taken and not _groups_of(candidate):
            take(candidate, OTHER_GROUP["key"])

    order_of = {group["key"]: index for index, group in enumerate(groups_of(template))}
    chosen.sort(key=lambda row: (order_of.get(row[1], 99), _rank_key(row[0])))
    SquadPick.objects.bulk_create(
        [
            pick_from(candidate, squad, group_key, locked=False, order=index + 1)
            for index, (candidate, group_key) in enumerate(chosen)
        ]
    )
    squad.generated_at = timezone.now()
    if by is not None:
        squad.selected_by = by
    squad.save(update_fields=["generated_at", "selected_by", "updated_at"])
    return list(squad.picks.all())
