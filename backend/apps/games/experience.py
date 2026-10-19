"""The Games experience: opening screen, NOC, athlete and event pages, records,
follows and alerts, and the local-games points table.

Everything here reads the event competitions' own results; no sport is named.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import (
    NOC,
    Athlete,
    Games,
    GamesAlert,
    GamesEvent,
    GamesFollow,
    GamesRecord,
    Medal,
    MedalChange,
)

# Result types where a smaller mark is better; used for "best at these Games".
LOWER_FIRST = {"timed_lowest", "multi_run_aggregate", "points_lowest", "penalty_total_lowest"}
# Result types whose mark is a place, not a performance worth calling a best.
NO_MARK = {"finishing_order", "combat_decision"}


def _decimal_text(value) -> str:
    if value is None:
        return ""
    text = format(Decimal(value).normalize(), "f")
    return text


def event_label(event: GamesEvent) -> str:
    return f"{event.sport_label}: {event.name}"


def _event_brief(event: GamesEvent) -> dict:
    return {
        "id": str(event.id),
        "sport_key": event.sport_key,
        "sport": event.sport_label,
        "name": event.name,
        "venue": event.venue,
        "scheduled_at": event.scheduled_at,
        "status": event.status,
    }


# --- Results, round by round ----------------------------------------------------------


def _side_rows(fixture, entries: dict) -> list[dict]:
    """Every entrant in one fixture with their place and mark."""

    sheet = getattr(fixture, "result_sheet", None)
    rows = []
    for side in fixture.sides.all():
        entry = entries.get(side.participant_id)
        result = getattr(side, "entry_result", None) if sheet is not None else None
        row = {
            "participant_id": str(side.participant_id),
            "name": side.participant.name,
            "noc": entry.noc.code if entry else "",
            "noc_id": str(entry.noc_id) if entry else None,
            "athlete_id": str(entry.athlete_id) if entry and entry.athlete_id else None,
            "position": side.position,
        }
        if result is not None:
            row.update(
                {
                    "rank": result.rank,
                    "mark": _decimal_text(result.primary),
                    "status": result.effective_status,
                    "qualified": str((result.data or {}).get("qualified") or ""),
                }
            )
        else:
            places = {"win": 1, "draw": 1, "loss": 2}
            row.update(
                {
                    "rank": places.get(side.outcome),
                    "mark": _decimal_text(side.score),
                    "status": "",
                    "qualified": "",
                    "outcome": side.outcome,
                }
            )
        rows.append(row)
    rows.sort(key=lambda item: (item["rank"] is None, item["rank"] or 0, item["position"]))
    return rows


def event_rounds(event: GamesEvent) -> list[dict]:
    """Start lists and results for every round (heat, semi-final, final, match)."""

    entries = {entry.participant_id: entry for entry in event.entries.select_related("noc")}
    fixtures = (
        event.competition.fixtures.select_related("result_sheet")
        .prefetch_related("sides__participant", "sides__entry_result")
        .order_by("round_number", "scheduled_at", "created_at")
    )
    rounds = []
    for fixture in fixtures:
        sheet = getattr(fixture, "result_sheet", None)
        rounds.append(
            {
                "fixture_id": str(fixture.id),
                "label": fixture.label
                or (f"Round {fixture.round_number}" if fixture.round_number else "Match"),
                "round": fixture.round_number,
                "status": fixture.status,
                "scheduled_at": fixture.scheduled_at,
                "final": bool(sheet and sheet.is_final),
                "start_list": [
                    {
                        "position": side.position + 1,
                        "name": side.participant.name,
                        "noc": entries[side.participant_id].noc.code
                        if side.participant_id in entries
                        else "",
                    }
                    for side in sorted(fixture.sides.all(), key=lambda item: item.position)
                ],
                "results": _side_rows(fixture, entries),
            }
        )
    return rounds


def record_row(record: GamesRecord) -> dict:
    return {
        "id": str(record.id),
        "event_id": str(record.event_id),
        "event": event_label(record.event),
        "scope": record.scope,
        "scope_label": record.get_scope_display(),
        "mark": record.mark,
        "previous_mark": record.previous_mark,
        "holder": record.holder,
        "noc": record.noc.code if record.noc_id else "",
        "athlete_id": str(record.athlete_id) if record.athlete_id else None,
        "set_on": record.set_on,
        "note": record.note,
    }


def add_record(event: GamesEvent, data: dict, actor) -> GamesRecord:
    from rest_framework.exceptions import ValidationError

    scope = str(data.get("scope") or "")
    if scope not in GamesRecord.Scope.values:
        raise ValidationError({"scope": "Choose a Games, national or world record."})
    mark = str(data.get("mark") or "").strip()
    if not mark:
        raise ValidationError({"mark": "Give the record mark."})
    athlete = None
    if data.get("athlete"):
        athlete = Athlete.objects.filter(pk=data["athlete"], games=event.games).first()
        if athlete is None:
            raise ValidationError({"athlete": "That athlete is not in this Games."})
    noc = athlete.noc if athlete else None
    if data.get("noc") and noc is None:
        noc = NOC.objects.filter(pk=data["noc"], games=event.games).first()
    holder = str(data.get("holder") or (athlete.name if athlete else "")).strip()
    if not holder:
        raise ValidationError({"holder": "Who set the record?"})
    return GamesRecord.objects.create(
        games=event.games,
        event=event,
        scope=scope,
        mark=mark[:40],
        previous_mark=str(data.get("previous_mark") or "")[:40],
        holder=holder[:160],
        noc=noc,
        athlete=athlete,
        set_on=data.get("set_on") or timezone.localdate(),
        note=str(data.get("note") or "")[:240],
        added_by=actor,
    )


# --- Opening screen --------------------------------------------------------------------


def _countdown(games: Games, today: date) -> dict:
    if games.starts_on is None:
        return {"state": "unscheduled", "days_to_go": None, "day": None}
    if today < games.starts_on:
        return {"state": "upcoming", "days_to_go": (games.starts_on - today).days, "day": None}
    if games.ends_on and today > games.ends_on:
        return {"state": "finished", "days_to_go": 0, "day": None}
    return {"state": "live", "days_to_go": 0, "day": (today - games.starts_on).days + 1}


def _sessions(games: Games, start: datetime, end: datetime) -> list[dict]:
    """Every event and fixture scheduled between two moments, earliest first."""

    from apps.fixtures.models import Fixture

    sessions = []
    events = {event.competition_id: event for event in games.events.all()}
    fixtures = Fixture.objects.filter(
        competition_id__in=events, scheduled_at__gte=start, scheduled_at__lt=end
    ).order_by("scheduled_at")
    with_fixtures = set()
    for fixture in fixtures:
        event = events[fixture.competition_id]
        with_fixtures.add(event.id)
        sessions.append(
            {
                **_event_brief(event),
                "fixture_id": str(fixture.id),
                "session": fixture.label,
                "at": fixture.scheduled_at,
                "fixture_status": fixture.status,
            }
        )
    for event in games.events.filter(scheduled_at__gte=start, scheduled_at__lt=end):
        if event.id not in with_fixtures:
            sessions.append(
                {
                    **_event_brief(event),
                    "fixture_id": None,
                    "session": "",
                    "at": event.scheduled_at,
                    "fixture_status": "",
                }
            )
    sessions.sort(key=lambda row: row["at"])
    return sessions


def overview(games: Games, now: datetime | None = None) -> dict:
    from apps.fixtures.models import Fixture

    from .services import medal_feed, medal_table

    now = now or timezone.now()
    today = timezone.localdate(now)
    start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    events = {event.competition_id: event for event in games.events.all()}
    live = [
        {
            **_event_brief(events[fixture.competition_id]),
            "fixture_id": str(fixture.id),
            "session": fixture.label,
        }
        for fixture in Fixture.objects.filter(
            competition_id__in=events, status=Fixture.Status.LIVE
        ).order_by("scheduled_at", "created_at")
    ]
    return {
        "countdown": _countdown(games, today),
        "today": _sessions(games, start, start + timedelta(days=1)),
        "live": live,
        "medal_table": medal_table(games)[:10],
        "latest_medals": medal_feed(games, limit=8),
        "points_table": points_table(games) if games.placing_points else [],
        "records": [record_row(row) for row in games.records.select_related("event", "noc")[:5]],
    }


# --- Local games: points per placing -----------------------------------------------------


def points_table(games: Games) -> list[dict]:
    """Points per placing across every decided event; equal places earn the same points."""

    from .services import medal_table, ranking

    points = [Decimal(str(value)) for value in games.placing_points or []]
    medals = {row["noc_id"]: row for row in medal_table(games)}
    rows = {
        str(noc.id): {
            "noc_id": str(noc.id),
            "code": noc.code,
            "name": noc.name,
            "colour": noc.colour,
            "points": Decimal("0"),
            "placings": 0,
            "gold": medals.get(str(noc.id), {}).get("gold", 0),
            "silver": medals.get(str(noc.id), {}).get("silver", 0),
            "bronze": medals.get(str(noc.id), {}).get("bronze", 0),
        }
        for noc in games.nocs.all()
    }
    if points:
        decided = games.events.filter(status=GamesEvent.Status.MEDALS_AWARDED)
        for event in decided.select_related("competition"):
            entries = {str(entry.participant_id): entry for entry in event.entries.all()}
            for participant_id, rank in ranking(event) or []:
                entry = entries.get(participant_id)
                if entry is None or rank is None or rank > len(points):
                    continue
                row = rows[str(entry.noc_id)]
                row["points"] += points[rank - 1]
                row["placings"] += 1
    ordered = sorted(
        rows.values(),
        key=lambda row: (-row["points"], -row["gold"], -row["silver"], -row["bronze"], row["code"]),
    )
    previous = None
    for index, row in enumerate(ordered):
        if row["points"] != previous:
            row["rank"] = index + 1
            previous = row["points"]
        else:
            row["rank"] = ordered[index - 1]["rank"]
        row["points"] = _decimal_text(row["points"]) or "0"
    return ordered


# --- NOC and athlete pages ------------------------------------------------------------------


def _best_marks(results: list[dict]) -> list[dict]:
    """The best mark per event at these Games."""

    best: dict[str, dict] = {}
    for row in results:
        if not row["mark"] or row["result_type"] in NO_MARK or row["status"]:
            continue
        current = best.get(row["event_id"])
        lower = row["result_type"] in LOWER_FIRST
        value = Decimal(row["mark"])
        if current is None or (
            value < Decimal(current["mark"]) if lower else value > Decimal(current["mark"])
        ):
            best[row["event_id"]] = {
                "event_id": row["event_id"],
                "event": row["event"],
                "mark": row["mark"],
            }
    return list(best.values())


def _entry_results(entries) -> list[dict]:
    rows = []
    for entry in entries:
        event = entry.event
        result_type = (event.competition.settings_json or {}).get("result_type") or ""
        for side in entry.participant.fixture_sides.select_related(
            "fixture", "fixture__result_sheet", "entry_result"
        ).order_by("fixture__round_number", "fixture__scheduled_at", "fixture__created_at"):
            fixture = side.fixture
            result = getattr(side, "entry_result", None)
            sheet = getattr(fixture, "result_sheet", None)
            rows.append(
                {
                    "event_id": str(event.id),
                    "event": event_label(event),
                    "result_type": result_type,
                    "round": fixture.label or "Match",
                    "fixture_status": fixture.status,
                    "final": bool(sheet and sheet.is_final),
                    "rank": result.rank if result else {"win": 1, "loss": 2}.get(side.outcome),
                    "mark": _decimal_text(result.primary if result else side.score),
                    "status": result.effective_status if result else "",
                    "qualified": str(
                        ((result.data if result else None) or {}).get("qualified") or ""
                    ),
                }
            )
    return rows


def _medal_rows(medals) -> list[dict]:
    return [
        {
            "event_id": str(medal.event_id),
            "event": event_label(medal.event),
            "sport": medal.event.sport_label,
            "medal": medal.medal,
            "entrant": medal.entry.participant.name,
        }
        for medal in medals.select_related("event", "entry__participant").order_by(
            "event__sport_label", "rank"
        )
    ]


def noc_page(noc: NOC) -> dict:
    entries = noc.entries.select_related("event__competition", "participant", "athlete")
    results = _entry_results(entries)
    by_sport: dict = defaultdict(lambda: {"gold": 0, "silver": 0, "bronze": 0})
    medals = _medal_rows(noc.medals.all())
    for medal in medals:
        by_sport[medal["sport"]][medal["medal"]] += 1
    return {
        "id": str(noc.id),
        "code": noc.code,
        "name": noc.name,
        "flag_url": noc.flag_url,
        "colour": noc.colour,
        "athletes": [
            {"id": str(athlete.id), "name": athlete.name, "events": athlete.entries.count()}
            for athlete in noc.athletes.all()
        ],
        "entries": [
            {
                "event_id": str(entry.event_id),
                "event": event_label(entry.event),
                "entrant": entry.participant.name,
                "athlete_id": str(entry.athlete_id) if entry.athlete_id else None,
            }
            for entry in entries
        ],
        "results": results,
        "medals": medals,
        "medals_by_sport": [
            {"sport": sport, **counts} for sport, counts in sorted(by_sport.items())
        ],
        "records": [
            record_row(row) for row in noc.games.records.filter(noc=noc).select_related("event")
        ],
    }


def athlete_page(athlete: Athlete, viewer=None) -> dict:
    entries = athlete.entries.select_related("event__competition", "participant")
    results = _entry_results(entries)
    profile_id = None
    if athlete.user_id:
        from apps.scouting.models import PlayerProfile

        profile = PlayerProfile.objects.filter(user_id=athlete.user_id).first()
        if profile is not None and (
            profile.visibility != PlayerProfile.Visibility.PRIVATE
            or getattr(viewer, "id", None) == athlete.user_id
        ):
            profile_id = str(profile.id)
    return {
        "id": str(athlete.id),
        "name": athlete.name,
        "noc": athlete.noc.code,
        "noc_id": str(athlete.noc_id),
        "noc_name": athlete.noc.name,
        "events": [_event_brief(entry.event) for entry in entries],
        "results": results,
        "personal_bests": list(athlete.personal_bests or []),
        "best_at_games": _best_marks(results),
        "medals": _medal_rows(Medal.objects.filter(entry__athlete=athlete)),
        "records": [record_row(row) for row in athlete.records.select_related("event", "noc")],
        "scouting_profile_id": profile_id,
    }


# --- Follows and alerts ------------------------------------------------------------------------


def follow_row(follow: GamesFollow) -> dict:
    label = {
        GamesFollow.Target.NOC: lambda: (
            f"{follow.noc.code} {follow.noc.name}" if follow.noc else ""
        ),
        GamesFollow.Target.ATHLETE: lambda: follow.athlete.name if follow.athlete else "",
        GamesFollow.Target.SPORT: lambda: next(
            (row.sport_label for row in follow.games.events.filter(sport_key=follow.sport_key)[:1]),
            follow.sport_key,
        ),
    }[follow.target]()
    return {
        "id": str(follow.id),
        "target": follow.target,
        "noc_id": str(follow.noc_id) if follow.noc_id else None,
        "athlete_id": str(follow.athlete_id) if follow.athlete_id else None,
        "sport_key": follow.sport_key,
        "label": label,
    }


def add_follow(games: Games, user, data: dict) -> GamesFollow:
    from rest_framework.exceptions import ValidationError

    target = str(data.get("target") or "")
    values = {"noc": None, "athlete": None, "sport_key": ""}
    if target == GamesFollow.Target.NOC:
        values["noc"] = NOC.objects.filter(pk=data.get("noc"), games=games).first()
        if values["noc"] is None:
            raise ValidationError({"noc": "That NOC is not in this Games."})
    elif target == GamesFollow.Target.ATHLETE:
        values["athlete"] = Athlete.objects.filter(pk=data.get("athlete"), games=games).first()
        if values["athlete"] is None:
            raise ValidationError({"athlete": "That athlete is not in this Games."})
    elif target == GamesFollow.Target.SPORT:
        sport_key = str(data.get("sport_key") or "")
        if not games.events.filter(sport_key=sport_key).exists():
            raise ValidationError({"sport_key": "That sport is not in this Games."})
        values["sport_key"] = sport_key
    else:
        raise ValidationError({"target": "Follow an NOC, a sport or an athlete."})
    follow, _ = GamesFollow.objects.get_or_create(games=games, user=user, target=target, **values)
    return follow


def followers(event: GamesEvent, nocs=None, athletes=None) -> list:
    """Everyone following this event's sport, or one of the NOCs or athletes in it."""

    nocs = set(nocs if nocs is not None else event.entries.values_list("noc_id", flat=True))
    athletes = set(
        athletes
        if athletes is not None
        else event.entries.exclude(athlete=None).values_list("athlete_id", flat=True)
    )
    follows = GamesFollow.objects.filter(games_id=event.games_id).filter(
        Q(target=GamesFollow.Target.SPORT, sport_key=event.sport_key)
        | Q(target=GamesFollow.Target.NOC, noc_id__in=nocs)
        | Q(target=GamesFollow.Target.ATHLETE, athlete_id__in=athletes)
    )
    seen, users = set(), []
    for follow in follows.select_related("user"):
        if follow.user_id not in seen and follow.user.is_active:
            seen.add(follow.user_id)
            users.append(follow.user)
    return users


def _send(
    users, event: GamesEvent, kind: str, key: str, *, title: str, body: str, category: str
) -> int:
    from apps.notifications.services import notify_users

    fresh = []
    for user in users:
        _, created = GamesAlert.objects.get_or_create(user=user, event=event, kind=kind, key=key)
        if created:
            fresh.append(user)
    if not fresh:
        return 0
    notify_users(
        fresh,
        kind=f"games.{kind}",
        title=title,
        body=body,
        competition=event.competition,
        category=category,
        data={"games_id": str(event.games_id), "event_id": str(event.id)},
    )
    return len(fresh)


def medals_changed(event: GamesEvent, change: MedalChange) -> None:
    """Push the new medal table to everyone watching, and alert followers."""

    from apps.core.bus import games_room, publish_event

    from .services import medal_table

    games = event.games
    publish_event(
        "games.medals",
        {
            "games_id": str(games.id),
            "event_id": str(event.id),
            "event": event_label(event),
            "table": medal_table(games),
            "points_table": points_table(games) if games.placing_points else [],
        },
        [games_room(games.id)],
    )
    medals = list(event.medals.select_related("noc", "entry__participant").order_by("rank"))
    if not medals and not change.before:
        return
    body = (
        " · ".join(
            f"{medal.get_medal_display()} {medal.noc.code} {medal.entry.participant.name}"
            for medal in medals
        )
        or "Medals withdrawn pending a decision."
    )
    if change.before:
        body = f"Medals changed: {body}"
    _send(
        followers(event),
        event,
        GamesAlert.Kind.RESULT,
        str(change.id),
        title=event_label(event),
        body=body[:400],
        category="score_updates",
    )


def send_start_alerts(
    games: Games | None = None, *, now: datetime | None = None, minutes: int = 30
) -> int:
    """Alert followers of every session that starts within the next ``minutes``."""

    now = now or timezone.now()
    end = now + timedelta(minutes=minutes)
    sent = 0
    every = [games] if games is not None else Games.objects.exclude(status=Games.Status.COMPLETED)
    for row in every:
        for session in _sessions(row, now, end):
            if session["fixture_status"] not in ("", "scheduled"):
                continue
            event = GamesEvent.objects.select_related("competition", "games").get(pk=session["id"])
            when = timezone.localtime(session["at"]).strftime("%H:%M")
            what = f"{session['session']} " if session["session"] else ""
            nocs = athletes = None
            if session["fixture_id"]:
                in_fixture = event.entries.filter(
                    participant__fixture_sides__fixture_id=session["fixture_id"]
                )
                nocs = set(in_fixture.values_list("noc_id", flat=True))
                athletes = set(
                    in_fixture.exclude(athlete=None).values_list("athlete_id", flat=True)
                )
            sent += _send(
                followers(event, nocs, athletes),
                event,
                GamesAlert.Kind.START,
                session["fixture_id"] or "event",
                title=f"Starting soon: {event_label(event)}",
                body=f"{what}at {when}{' · ' + event.venue if event.venue else ''}".strip(),
                category="fixture_reminders",
            )
    return sent
