"""Fill a soccer competition with a complete FPL-style sample.

Assigns shirt numbers and positions, plays a few fixtures so players have
points and prices, then saves a handful of manager squads.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.competitions.models import Competition, Membership, RosterMember
from apps.fantasy.models import FantasyTeam
from apps.fantasy.rules import max_per_club_for
from apps.fantasy.services import auto_pick, market, save_team
from apps.fixtures.models import Fixture, PlayerAppearance, ScoreEvent
from apps.media_assets.models import MediaAsset
from apps.social.live import backfill_competition
from apps.social.models import Comment, CommentMedia, Post, PostMedia

PHOTO_PITCH = (
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018"
    "?auto=format&fit=crop&w=1200&q=80"
)
PHOTO_CROWD = (
    "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d"
    "?auto=format&fit=crop&w=1200&q=80"
)
PHOTO_KIT = (
    "https://images.unsplash.com/photo-1517927033932-b3d18e61fb3a"
    "?auto=format&fit=crop&w=1200&q=80"
)
CLIP_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4"
CLIP_POSTER = (
    "https://images.unsplash.com/photo-1517466787929-bc90951d0974"
    "?auto=format&fit=crop&w=1200&q=80"
)

User = get_user_model()

# One 14-man club list: 2 GK, 5 DEF, 5 MID, 2 FWD.
SHIRTS = [
    (1, "Goalkeeper"),
    (13, "Goalkeeper"),
    (2, "Right-back"),
    (3, "Centre-back"),
    (4, "Centre-back"),
    (5, "Left-back"),
    (6, "Centre-back"),
    (8, "Defensive midfield"),
    (7, "Winger"),
    (10, "Attacking midfield"),
    (11, "Winger"),
    (14, "Central midfield"),
    (9, "Striker"),
    (19, "Striker"),
]


class Command(BaseCommand):
    help = "Seed fantasy shirts, match stats and sample squads on a competition."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--name",
            default="Testing football",
            help="Competition to fill.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        name = options["name"]
        competition = Competition.objects.filter(name__iexact=name).first()
        if competition is None:
            raise CommandError(f"No competition named {name!r}.")

        shirts = self._assign_shirts(competition)
        played = self._play_fixtures(competition)
        managers = self._sample_squads(competition)
        posts = self._seed_feed(competition)
        live = backfill_competition(competition)

        self.stdout.write(
            self.style.SUCCESS(
                f"{competition.name}: {shirts} shirts, {played} matches scored, "
                f"{managers} fantasy teams, {posts} social posts, {live} live updates."
            )
        )

    def _assign_shirts(self, competition: Competition) -> int:
        updated = 0
        for team in competition.participants.prefetch_related("roster"):
            members = list(team.roster.filter(is_active=True).order_by("name"))
            for index, member in enumerate(members):
                number, position = SHIRTS[index % len(SHIRTS)]
                if member.number == number and member.position == position:
                    continue
                member.number = number
                member.position = position
                member.save(update_fields=["number", "position", "updated_at"])
                updated += 1
        return updated

    def _play_fixtures(self, competition: Competition) -> int:
        categories = {row.code: row for row in competition.scoring_categories.all()}
        needed = ["goal", "assist", "yellow-card", "save"]
        if any(code not in categories for code in needed):
            raise CommandError("This competition is missing soccer scoring types.")

        played = 0
        for fixture in competition.fixtures.prefetch_related("sides__participant__roster").order_by(
            "created_at"
        ):
            if fixture.status == Fixture.Status.LIVE:
                continue
            if fixture.status == Fixture.Status.COMPLETED and fixture.events.exists():
                continue
            sides = list(fixture.sides.all())
            if len(sides) < 2:
                continue
            self._play_one(fixture, sides, categories)
            played += 1
        return played

    def _play_one(self, fixture: Fixture, sides, categories) -> None:
        scripts = (
            [(12, "goal"), (12, "assist"), (8, "goal"), (3, "yellow-card"), (0, "save"), (0, "save"), (0, "save")],
            [(12, "goal"), (9, "assist"), (4, "yellow-card"), (0, "save"), (0, "save")],
        )
        for side, script in zip(sides, scripts, strict=False):
            squad = list(side.participant.roster.filter(is_active=True).order_by("number", "name"))
            if len(squad) < 11:
                continue
            xi = squad[:11]
            for player in xi:
                PlayerAppearance.objects.update_or_create(
                    fixture=fixture,
                    player=player,
                    defaults={"minutes": 90 if player.number != 14 else 62},
                )
            for minute, (index, code) in enumerate(script, start=8):
                if index >= len(squad):
                    continue
                ScoreEvent.objects.create(
                    fixture=fixture,
                    side=side,
                    scoring_category=categories[code],
                    player=squad[index],
                    player_name=squad[index].name,
                    quantity=Decimal("1"),
                    minute=minute * 7,
                )
        fixture.status = Fixture.Status.COMPLETED
        started = timezone.now() - timedelta(days=3)
        fixture.started_at = started
        fixture.completed_at = started + timedelta(minutes=95)
        fixture.duration_minutes = fixture.duration_minutes or 90
        fixture.save(update_fields=["status", "started_at", "completed_at", "duration_minutes"])
        fixture.recalculate_scores()

    def _sample_squads(self, competition: Competition) -> int:
        emails = [
            "account2@gmail.com",
            "ama@example.com",
            "tank@gmail.com",
            "junior@example.com",
        ]
        created = 0
        base = auto_pick(competition)
        for index, email in enumerate(emails):
            user = User.objects.filter(email=email).first()
            if user is None:
                continue
            if FantasyTeam.objects.filter(competition=competition, user=user).exists():
                continue
            save_team(
                competition,
                user,
                name=f"{user.display_name}'s XI",
                raw_picks=_vary_squad(competition, base, index),
            )
            created += 1
        return created

    def _authors(self, competition: Competition) -> list:
        emails = [
            "account2@gmail.com",
            "ama@example.com",
            "tank@gmail.com",
            "junior@example.com",
        ]
        users = list(User.objects.filter(email__in=emails))
        if competition.owner_id:
            users = [competition.owner, *[user for user in users if user.id != competition.owner_id]]
        if not users:
            member_ids = Membership.objects.filter(competition=competition).values_list(
                "user_id", flat=True
            )
            users = list(User.objects.filter(id__in=member_ids)[:4])
        return users

    def _image(self, owner, competition: Competition, url: str, caption: str) -> MediaAsset:
        asset, _ = MediaAsset.objects.get_or_create(
            owner=owner,
            competition=competition,
            storage_key=url,
            defaults={
                "kind": MediaAsset.Kind.IMAGE,
                "status": MediaAsset.Status.READY,
                "storage_provider": "remote",
                "caption": caption,
                "content_type": "image/jpeg",
                "width": 1200,
                "height": 800,
                "ready_at": timezone.now(),
            },
        )
        return asset

    def _video(self, owner, competition: Competition) -> MediaAsset:
        asset, _ = MediaAsset.objects.get_or_create(
            owner=owner,
            competition=competition,
            playback_url=CLIP_URL,
            defaults={
                "kind": MediaAsset.Kind.VIDEO,
                "status": MediaAsset.Status.READY,
                "caption": "Match clip",
                "thumbnail_url": CLIP_POSTER,
                "duration_seconds": 15,
                "content_type": "video/mp4",
                "ready_at": timezone.now(),
            },
        )
        return asset

    def _post(self, competition, author, body: str, **kwargs) -> Post:
        post, created = Post.objects.get_or_create(
            competition=competition,
            author=author,
            body=body,
            defaults=kwargs,
        )
        return post, created

    def _attach(self, post: Post, assets: list[MediaAsset]) -> None:
        for index, asset in enumerate(assets):
            PostMedia.objects.get_or_create(
                post=post,
                media_asset=asset,
                defaults={"display_order": index},
            )

    def _comment(self, post: Post, author, body: str, assets: list[MediaAsset] | None = None) -> None:
        comment, created = Comment.objects.get_or_create(
            post=post,
            author=author,
            body=body,
        )
        if created:
            Post.objects.filter(pk=post.pk).update(comment_count=post.comment_count + 1)
            post.comment_count += 1
        for index, asset in enumerate(assets or []):
            CommentMedia.objects.get_or_create(
                comment=comment,
                media_asset=asset,
                defaults={"display_order": index},
            )

    def _seed_feed(self, competition: Competition) -> int:
        authors = self._authors(competition)
        if not authors:
            return 0
        owner, *rest = authors
        ama = rest[0] if rest else owner
        tank = rest[1] if len(rest) > 1 else owner
        junior = rest[2] if len(rest) > 2 else ama

        pitch = self._image(owner, competition, PHOTO_PITCH, "Pitch-side")
        crowd = self._image(ama, competition, PHOTO_CROWD, "The crowd")
        kit = self._image(tank, competition, PHOTO_KIT, "New kit")
        clip = self._video(junior, competition)

        samples = [
            (
                owner,
                "Round 1 is live — Amaphara 3–0 lolipop. Fantasy captains are locked.",
                {"is_announcement": True, "kind": Post.Kind.COMPETITION},
                [],
                [
                    (ama, "What a start. Carmen Adams is unplayable."),
                    (tank, "Lolipop need a reset before Saturday."),
                ],
            ),
            (
                ama,
                "Training pictures from this morning. Who's starting at the weekend?",
                {},
                [pitch, crowd],
                [
                    (tank, "That back four looks set."),
                    (junior, "Drop the XI in the comments."),
                ],
            ),
            (
                junior,
                "Clip from the last goal. Rewatch and tell me that wasn't offside.",
                {},
                [clip],
                [(ama, "Onside. The full-back played him on.")],
            ),
            (
                tank,
                "Just picked my Fantasy XI. Carmen Adams captaining — already 27 points.",
                {},
                [],
                [(owner, "Bold. I'm vice-ing Farai Eze.")],
            ),
            (
                ama,
                "New kit drop. Home and away. Photos attached — say which one we wear Sunday.",
                {},
                [kit, pitch],
                [(junior, "", [kit])],
            ),
        ]

        written = 0
        for author, body, extras, media, comments in samples:
            post, created = self._post(competition, author, body, **extras)
            if created:
                written += 1
            self._attach(post, media)
            for comment in comments:
                if len(comment) == 3:
                    self._comment(post, comment[0], comment[1], comment[2])
                else:
                    self._comment(post, comment[0], comment[1])
        return written


def _vary_squad(competition, picks: list[dict], offset: int) -> list[dict]:
    """Keep a legal shape, but give each manager a slightly different XI."""

    if offset == 0:
        return picks
    available = market(competition)
    by_id = {player["id"]: player for player in available}
    used = {pick["player"] for pick in picks}
    clubs = Counter(by_id[pick["player"]]["team_id"] for pick in picks if pick["player"] in by_id)
    club_limit = max_per_club_for(len({player["team_id"] for player in available}))
    varied = []
    swaps = 0
    for pick in picks:
        current = by_id.get(pick["player"])
        replacement = None
        if swaps < offset and current:
            replacement = next(
                (
                    player
                    for player in available
                    if player["slot"] == pick["slot"]
                    and player["id"] not in used
                    and clubs[player["team_id"]] < club_limit
                ),
                None,
            )
        if replacement and current:
            used.discard(current["id"])
            used.add(replacement["id"])
            clubs[current["team_id"]] -= 1
            clubs[replacement["team_id"]] += 1
            varied.append({**pick, "player": replacement["id"]})
            swaps += 1
        else:
            varied.append(pick)
    return varied
