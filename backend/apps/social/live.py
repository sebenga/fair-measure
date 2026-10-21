"""Turn match events into feed posts: kick-off, goals, cards, full time.

Each generated row is tied to the competition and to a personal profile
(the player who did it, the scorer who recorded it, or the league owner).
"""

from __future__ import annotations

from apps.core.bus import competition_room, publish_event
from apps.fixtures.models import Fixture, ScoreEvent

from .models import Post

_HIGHLIGHT_CODES = {
    "goal",
    "try",
    "penalty-try",
    "own-goal",
    "assist",
    "yellow-card",
    "red-card",
    "second-yellow",
}


def _scoreline(fixture: Fixture) -> str:
    sides = list(fixture.sides.all())
    if len(sides) < 2:
        return fixture.label or "Match"
    return " – ".join(f"{side.participant.name} {side.score}" for side in sides[:2])


def _fixture_title(fixture: Fixture) -> str:
    if fixture.label:
        return fixture.label
    names = " v ".join(side.participant.name for side in fixture.sides.all()[:2])
    return names or "Match"


def _is_highlight(event: ScoreEvent) -> bool:
    code = (event.scoring_category.code or "").strip().lower()
    if code in _HIGHLIGHT_CODES or code.endswith("-card"):
        return True
    return bool(event.scoring_category.affects_score)


def _author_for_event(event: ScoreEvent):
    player = event.player
    if player is not None and player.user_id:
        return player.user
    if event.recorded_by_id:
        return event.recorded_by
    return event.fixture.competition.owner


def _upsert(
    *,
    competition,
    author,
    body: str,
    key: str,
    fixture: Fixture | None = None,
    participant=None,
    created_at=None,
) -> Post:
    existing = Post.objects.filter(source_key=key).alive().first()
    if existing:
        return existing

    post = Post.objects.create(
        competition=competition,
        author=author,
        body=body,
        kind=Post.Kind.LIVE,
        source_key=key,
        fixture=fixture,
        participant=participant,
    )
    if created_at:
        Post.objects.filter(pk=post.pk).update(created_at=created_at)
        post.created_at = created_at

    publish_event(
        "post.created",
        {
            "competition_id": str(competition.id),
            "post_id": str(post.id),
            "author_id": str(author.id),
            "kind": Post.Kind.LIVE,
        },
        [competition_room(competition.id)],
    )
    return post


def publish_kickoff(fixture: Fixture) -> Post | None:
    fixture.refresh_from_db()
    if fixture.status not in {Fixture.Status.LIVE, Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
        return None
    competition = fixture.competition
    if competition.owner_id is None:
        return None
    title = _fixture_title(fixture)
    return _upsert(
        competition=competition,
        author=competition.owner,
        body=f"Kick-off · {title} is live.",
        key=f"live:{fixture.id}:kickoff",
        fixture=fixture,
        created_at=fixture.started_at,
    )


def publish_full_time(fixture: Fixture) -> Post | None:
    fixture.refresh_from_db()
    if fixture.status not in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
        return None
    competition = fixture.competition
    if competition.owner_id is None:
        return None
    line = _scoreline(fixture)
    verb = "Forfeit" if fixture.status == Fixture.Status.FORFEIT else "Full time"
    return _upsert(
        competition=competition,
        author=competition.owner,
        body=f"{verb} · {line}",
        key=f"live:{fixture.id}:ft",
        fixture=fixture,
        created_at=fixture.completed_at,
    )


def publish_score_event(event: ScoreEvent) -> Post | None:
    event = (
        ScoreEvent.objects.select_related(
            "fixture__competition__owner",
            "side__participant",
            "scoring_category",
            "player__user",
            "recorded_by",
        )
        .prefetch_related("fixture__sides__participant")
        .get(pk=event.pk)
    )
    if not _is_highlight(event):
        return None

    fixture = event.fixture
    competition = fixture.competition
    player = event.player_name or (event.player.name if event.player else "Someone")
    team = event.side.participant.name
    minute = f"{event.minute}' " if event.minute is not None else ""
    body = f"{event.scoring_category.name} · {minute}{player} ({team})\n{_scoreline(fixture)}"
    return _upsert(
        competition=competition,
        author=_author_for_event(event),
        body=body,
        key=f"live:{fixture.id}:event:{event.id}",
        fixture=fixture,
        participant=event.side.participant,
        created_at=event.occurred_at or event.created_at,
    )


def backfill_competition(competition) -> int:
    """Write live posts for matches that already have a result."""

    written = 0
    fixtures = (
        Fixture.objects.filter(competition=competition)
        .exclude(status=Fixture.Status.SCHEDULED)
        .select_related("competition__owner")
        .prefetch_related("sides__participant", "events__scoring_category", "events__side__participant")
    )
    for fixture in fixtures:
        before = Post.objects.filter(source_key__startswith=f"live:{fixture.id}:").count()
        publish_kickoff(fixture)
        for event in fixture.events.all():
            publish_score_event(event)
        if fixture.status in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
            publish_full_time(fixture)
        after = Post.objects.filter(source_key__startswith=f"live:{fixture.id}:").count()
        written += max(0, after - before)
    return written
