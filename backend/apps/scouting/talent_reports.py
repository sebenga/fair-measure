"""Scouting Phase 6: six talent reports, built only from stored data.

Every report is one document: a title, the organisation it is produced for, and a
list of sections (facts, tables, a radar, a line chart, notes, links, highlights).
The screen and the PDF render the same document. Reports apply the same visibility
and consent rules as the screens they summarise, and every number carries its date
and whether it was verified.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from . import attributes, catalog, ratings, search, stats
from .models import (
    Organisation,
    PlayerProfile,
    PlayerSport,
    PlayerStatLine,
    ScoutRating,
    Shortlist,
)
from .serializers import ScoutProfileSerializer
from .services import (
    access_level,
    age_group,
    is_scout_admin_of,
    scout_organisations,
    scouting_leagues,
)

KINDS = ("player", "progress", "compare", "shortlist", "competition", "activity")
TITLES = {
    "player": "Player scouting report",
    "progress": "Player progress report",
    "compare": "Comparison report",
    "shortlist": "Shortlist report",
    "competition": "Competition talent report",
    "activity": "Scout activity report",
}
ENGINE = "From recorded matches"


# --- Shapes ----------------------------------------------------------------------------


def _text(value) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def facts(heading: str, rows: list[dict], note: str = "") -> dict:
    return {"type": "facts", "heading": heading, "rows": rows, "note": note}


def fact(label: str, value, *, on=None, verified=None, source: str = "") -> dict:
    return {
        "label": label,
        "value": _text(value),
        "date": _text(on) if on else None,
        "verified": verified,
        "source": source,
    }


def table(heading: str, columns: list[str], rows: list[list], note: str = "", highlight=None) -> dict:
    return {
        "type": "table",
        "heading": heading,
        "columns": columns,
        "rows": [[_text(cell) for cell in row] for row in rows],
        "note": note,
        "highlight": highlight or [],
    }


def document(kind: str, *, subtitle: str, organisation: Organisation | None, sections: list, viewer, access: str = "") -> dict:
    return {
        "kind": kind,
        "title": TITLES[kind],
        "subtitle": subtitle,
        "generated_at": timezone.now(),
        "generated_for": viewer.display_name if viewer and viewer.is_authenticated else "",
        "access": access,
        "organisation": (
            {"id": str(organisation.id), "name": organisation.name, "logo_url": organisation.logo_url}
            if organisation
            else None
        ),
        "sections": [section for section in sections if section],
    }


def _organisation(viewer, organisation_id=None) -> Organisation | None:
    mine = scout_organisations(viewer)
    if organisation_id:
        found = next((row for row in mine if str(row.id) == str(organisation_id)), None)
        if found is None:
            raise PermissionDenied("You do not scout for that organisation.")
        return found
    return mine[0] if mine else None


def _visible(viewer, pk) -> tuple[PlayerProfile, str]:
    profile = PlayerProfile.objects.filter(pk=pk).select_related("user").first()
    access = access_level(profile, viewer) if profile else None
    if access is None:
        raise NotFound("No profile found.")
    return profile, access


def _sport(profile: PlayerProfile, sport: str | None) -> str:
    if sport:
        if sport not in catalog.SPORTS:
            raise ValidationError({"sport": "That sport is not in the scouting catalogue."})
        return sport
    primary = (
        PlayerSport.objects.filter(profile=profile, sport__in=list(catalog.SPORTS))
        .order_by("-is_primary")
        .first()
    )
    if primary:
        return primary.sport
    line = PlayerStatLine.objects.filter(user=profile.user, sport__in=list(catalog.SPORTS)).first()
    return line.sport if line else ""


def _position_label(sport: str, key: str) -> str:
    entry = catalog.sport_catalogue(sport) or {}
    return next((row["label"] for row in entry.get("positions", []) if row["key"] == key), key)


def _percentile_text(value, sample: int) -> str:
    if value is None:
        return f"hidden (fewer than {stats.MIN_SAMPLE} to compare)" if sample < stats.MIN_SAMPLE else "—"
    return f"{value:g}th"


def _key_stats(sport: str, limit: int = 6) -> list[dict]:
    entry = catalog.sport_catalogue(sport) or {}
    return [row for row in entry.get("match_stats", []) if row.get("better")][:limit]


# --- Shared sections --------------------------------------------------------------------


def tests_section(profile: PlayerProfile, sport: str, peers: list) -> dict | None:
    rows = stats.test_summary(profile, sport, peers)
    if not rows:
        return None
    return table(
        "Physical tests vs percentiles",
        ["Test", "Best", "Date", "Verified", "Percentile", "Trend"],
        [
            [
                row["label"],
                f"{row['personal_best']['value']:g} {row['unit']}",
                row["personal_best"]["tested_on"],
                row["personal_best"]["label"],
                _percentile_text(row["percentile"], row["sample"]),
                row["trend"] or "one result",
            ]
            for row in rows
        ],
        note=(
            f"Percentiles compare the best result with players of the same sport, position, age "
            f"group and gender category; hidden below {stats.MIN_SAMPLE}."
        ),
    )


def season_section(profile: PlayerProfile, sport: str, peers: list) -> dict | None:
    line = search.latest_line(profile, sport)
    if line is None:
        return None
    ranks = stats.stat_percentiles(profile, sport, line.season, line.values, peers)
    entry = catalog.sport_catalogue(sport) or {}
    rows = []
    for definition in entry.get("match_stats", []):
        value = (line.values.get(definition["key"]) or {})
        if value.get("value") is None:
            continue
        rank = ranks.get(definition["key"]) or {}
        rows.append(
            [
                definition["label"],
                value.get("value"),
                value.get("per_match"),
                _percentile_text(rank.get("percentile"), rank.get("sample", 0)),
            ]
        )
    if not rows:
        return None
    return table(
        f"Season {line.season} stats ({line.matches} matches)",
        ["Stat", "Value", "Per match", "Percentile"],
        rows,
        note=(
            f"{ENGINE}; computed {line.computed_at.date().isoformat()}. Counted from scored "
            "matches, not self-reported."
        ),
    )


def _ratings_visible(viewer, organisation: Organisation | None, access: str) -> bool:
    # Ratings and notes belong to the scout's organisation: never the player or guardian.
    return organisation is not None and access == "scout"


# --- 1. Player scouting report ----------------------------------------------------------


def player_report(viewer, pk, sport: str | None = None) -> dict:
    from .reports import league_record

    profile, access = _visible(viewer, pk)
    sport = _sport(profile, sport)
    shaped = "scout" if access in {"owner", "guardian"} else access
    view = ScoutProfileSerializer(profile, context={"access": shaped}).data
    organisation = _organisation(viewer) if access == "scout" else None
    peers = stats.cohort(profile, sport) if sport else []
    primary = next(iter(view["sports"]), None)
    sections: list = [
        facts(
            "Profile",
            [
                fact("Name", profile.full_name),
                fact("Age group", (view.get("age_group") or {}).get("label")),
                fact("Sport", catalog.SPORTS.get(sport, {}).get("label", sport) if sport else None),
                fact("Position", primary.get("primary_position_label") if primary else None),
                fact("Region", view.get("region")),
                fact("Club or school", view.get("school_or_club")),
                fact("Profile updated", view.get("updated_at")),
            ],
            note="Contact details are never included. Contact the player through Fair Measure.",
        ),
    ]
    if view.get("photo_url"):
        sections[0]["photo_url"] = view["photo_url"]
    if sport:
        sections.append(tests_section(profile, sport, peers))
        sections.append(season_section(profile, sport, peers))
    if view.get("measurements"):
        sections.append(
            table(
                "Measurements",
                ["Measure", "Value", "Date", "Verified"],
                [
                    [
                        row.get("label") or row.get("kind"),
                        f"{row.get('value') or row.get('text_value') or ''} {row.get('unit') or ''}".strip(),
                        row.get("measured_on"),
                        "Verified" if row.get("verified") else "Self-reported",
                    ]
                    for row in view["measurements"]
                ],
            )
        )

    if _ratings_visible(viewer, organisation, access):
        summary = ratings.summary(profile, organisation, sport or None)
        if summary["ratings"]:
            sections.append(
                {
                    "type": "radar",
                    "heading": f"The five areas ({organisation.name}, confidence-weighted)",
                    "axes": [row["label"] for row in summary["areas"]],
                    "series": [
                        {"name": profile.full_name, "values": [row["average"] for row in summary["areas"]]}
                    ],
                    "max": 10,
                    "note": f"{summary['scouts']} scout(s), {summary['ratings']} rating(s).",
                }
            )
            sections.append(
                {
                    "type": "line",
                    "heading": "Rating history",
                    "points": [
                        {"date": _text(row["observed_at"]), "value": row["average"], "label": row["scout"]}
                        for row in summary["progress"]
                        if row["average"] is not None
                    ],
                    "max": 10,
                }
            )
            top = max(summary["recommendations"], key=lambda row: row["count"])
            sections.append(
                facts(
                    "Ability and recommendation",
                    [
                        fact("Current ability", summary["current_ability"], source="Confidence-weighted, latest per scout"),
                        fact("Potential", summary["potential"], source="Confidence-weighted, latest per scout"),
                        fact(
                            "Recommendation",
                            f"{top['label']} ({top['count']} of {summary['scouts']})" if top["count"] else None,
                        ),
                    ],
                )
            )
            notes = (
                ScoutRating.objects.filter(profile=profile, organisation=organisation)
                .exclude(notes="")
                .select_related("scout")
                .order_by("-observed_at")
            )
            sections.append(
                {
                    "type": "notes",
                    "heading": f"Scouts' notes ({organisation.name} only)",
                    "items": [
                        {"author": row.scout.display_name, "date": _text(row.observed_at), "text": row.notes}
                        for row in notes
                    ],
                }
            )
        else:
            sections.append(facts("Scout ratings", [fact("Ratings", f"None yet from {organisation.name}")]))

    links = [
        {"label": row.get("title") or "Highlight", "url": row.get("playback_url") or row.get("url")}
        for row in view.get("videos") or []
        if row.get("playback_url") or row.get("url")
    ]
    if _ratings_visible(viewer, organisation, access):
        for rating in ScoutRating.objects.filter(profile=profile, organisation=organisation).exclude(clips=[]):
            for clip in rating.clips or []:
                url = clip.get("url") if isinstance(clip, dict) else str(clip)
                if url:
                    links.append({"label": f"Clip · {rating.observed_at.date().isoformat()}", "url": url})
    if links:
        sections.append({"type": "links", "heading": "Video", "items": links})

    leagues = league_record(profile, viewer)
    if leagues:
        sections.append(
            table(
                "League record (leagues open to scouts)",
                ["League", "Team", "Games", "W-D-L", "Avg match rating"],
                [
                    [
                        row["competition"],
                        row["team"],
                        row["games"],
                        f"{row['record']['won']}-{row['record']['drawn']}-{row['record']['lost']}",
                        row["avg_rating"],
                    ]
                    for row in leagues
                ],
            )
        )
    return document(
        "player",
        subtitle=f"{profile.full_name}{' · ' + catalog.SPORTS[sport]['label'] if sport else ''}",
        organisation=organisation,
        sections=sections,
        viewer=viewer,
        access=access,
    )


# --- 2. Player progress report ----------------------------------------------------------


def _parse(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError({"from": "Use dates like 2026-01-31."}) from error


def progress_report(viewer, pk, sport: str | None = None, start=None, end=None) -> dict:
    profile, access = _visible(viewer, pk)
    sport = _sport(profile, sport)
    start, end = _parse(start), _parse(end)
    organisation = _organisation(viewer) if access == "scout" else None
    improvements: list[tuple[float, str]] = []
    sections: list = []

    test_rows = []
    for row in stats.test_summary(profile, sport, []) if sport else []:
        history = [
            item
            for item in row["history"]
            if (not start or item["tested_on"] >= start) and (not end or item["tested_on"] <= end)
        ]
        if len(history) < 2:
            continue
        first, last = history[0], history[-1]
        change = last["value"] - first["value"]
        better = change < 0 if row["better"] == "lower" else change > 0
        share = abs(change) / first["value"] * 100 if first["value"] else 0
        if better and change:
            improvements.append((share, f"{row['label']}: {first['value']:g} → {last['value']:g} {row['unit']} ({share:.1f}% better)"))
        test_rows.append(
            [
                row["label"],
                f"{first['value']:g} {row['unit']} ({first['tested_on']}, {first['label']})",
                f"{last['value']:g} {row['unit']} ({last['tested_on']}, {last['label']})",
                f"{change:+g}",
                "better" if better and change else ("worse" if change else "same"),
            ]
        )
    if test_rows:
        sections.append(
            table(
                "Physical tests over time",
                ["Test", "First", "Latest", "Change", "Direction"],
                test_rows,
                highlight=[index for index, row in enumerate(test_rows) if row[-1] == "better"],
            )
        )

    lines = list(
        PlayerStatLine.objects.filter(user=profile.user, sport=sport, competition=None).order_by("season")
    )
    if start:
        lines = [line for line in lines if line.season >= start.year]
    if end:
        lines = [line for line in lines if line.season <= end.year]
    if len(lines) >= 2:
        first, last = lines[0], lines[-1]
        stat_rows = []
        for definition in _key_stats(sport, 10):
            before = (first.values.get(definition["key"]) or {}).get("per_match")
            after = (last.values.get(definition["key"]) or {}).get("per_match")
            if before is None or after is None:
                continue
            change = after - before
            better = change < 0 if definition["better"] == "lower" else change > 0
            if better and change and before:
                share = abs(change) / abs(before) * 100
                improvements.append((share, f"{definition['label']} per match: {before:g} → {after:g} ({share:.1f}% better)"))
            stat_rows.append([definition["label"], before, after, f"{change:+.2f}", "better" if better and change else ("worse" if change else "same")])
        if stat_rows:
            sections.append(
                table(
                    f"Match stats per match, season {first.season} → {last.season}",
                    ["Stat", str(first.season), str(last.season), "Change", "Direction"],
                    stat_rows,
                    note=f"{ENGINE}; computed {last.computed_at.date().isoformat()}.",
                    highlight=[index for index, row in enumerate(stat_rows) if row[-1] == "better"],
                )
            )

    if _ratings_visible(viewer, organisation, access):
        summary = ratings.summary(profile, organisation, sport or None)
        points = [
            row
            for row in summary["progress"]
            if row["average"] is not None
            and (not start or row["observed_at"].date() >= start)
            and (not end or row["observed_at"].date() <= end)
        ]
        if points:
            sections.append(
                {
                    "type": "line",
                    "heading": f"Average rating over time ({organisation.name})",
                    "points": [{"date": _text(row["observed_at"]), "value": row["average"], "label": row["scout"]} for row in points],
                    "max": 10,
                }
            )
            if len(points) >= 2 and points[-1]["average"] > points[0]["average"]:
                first, last = points[0]["average"], points[-1]["average"]
                share = (last - first) / first * 100
                improvements.append((share, f"Average scout rating: {first:g} → {last:g} ({share:.1f}% better)"))

    improvements.sort(reverse=True)
    sections.insert(
        0,
        {
            "type": "highlights",
            "heading": "Biggest improvements",
            "items": [text for _, text in improvements[:3]] or ["Not enough dated results to compare yet."],
        },
    )
    window = f"{start or 'start'} to {end or 'today'}"
    return document(
        "progress",
        subtitle=f"{profile.full_name} · {window}",
        organisation=organisation,
        sections=sections,
        viewer=viewer,
        access=access,
    )


# --- 3. Comparison report ---------------------------------------------------------------


def compare_report(viewer, ids: list[str], sport: str | None = None) -> dict:
    from .discovery_views import compare_data

    data = compare_data(viewer, ids, sport)
    organisation = _organisation(viewer)
    players = data["players"]
    sections: list = [
        {
            "type": "radar",
            "heading": "The five areas (your organisation's confidence-weighted ratings)",
            "axes": [area["label"] for area in data["areas"]],
            "series": [
                {"name": player["name"], "values": [player["areas"].get(area["key"]) for area in data["areas"]]}
                for player in players
            ],
            "max": 10,
        },
        table(
            "Players",
            ["Player", "Age group", "Position", "Current ability", "Potential", "Rated by"],
            [
                [
                    player["name"],
                    player["age_group"],
                    (player["sport"] or {}).get("primary_position_label"),
                    player["current_ability"],
                    player["potential"],
                    f"{player['rated_by']} scout(s)",
                ]
                for player in players
            ],
        ),
    ]
    if data["stats"]:
        sections.append(
            table(
                "Key stats (latest season, percentile in brackets)",
                ["Stat", *[player["name"] for player in players]],
                [
                    [
                        row["label"],
                        *[
                            (
                                f"{cell['value']:g}"
                                + (f" ({cell['percentile']:g}th)" if cell["percentile"] is not None else "")
                                if (cell := player["stats"][row["key"]])["value"] is not None
                                else None
                            )
                            for player in players
                        ],
                    ]
                    for row in data["stats"]
                ],
                note="; ".join(
                    f"{player['name']}: season {player['season']}, computed {_text(player['computed_at'])}"
                    for player in players
                    if player["season"]
                ),
            )
        )
    test_rows = []
    for row in data["tests"]:
        cells = []
        for player in players:
            best = player["tests"].get(row["key"])
            cells.append(
                f"{best['best']:g} {row['unit']} ({_text(best['tested_on'])}{'' if best['verified'] else ', self-reported'})"
                if best
                else None
            )
        if any(cells):
            test_rows.append([row["label"], *cells])
    if test_rows:
        sections.append(table("Physical tests (best result)", ["Test", *[player["name"] for player in players]], test_rows))
    return document(
        "compare",
        subtitle=" vs ".join(player["name"] for player in players),
        organisation=organisation,
        sections=sections,
        viewer=viewer,
        access="scout",
    )


# --- 4. Shortlist report ----------------------------------------------------------------


def shortlist_report(viewer, pk) -> dict:
    mine = {row.id: row for row in scout_organisations(viewer)}
    shortlist = Shortlist.objects.filter(pk=pk, organisation_id__in=list(mine)).first()
    if shortlist is None:
        raise NotFound("No shortlist found.")
    organisation = mine[shortlist.organisation_id]
    statuses = {row["key"]: row["label"] for row in attributes.SHORTLIST_STATUSES}
    recommendations = {row["key"]: row["label"] for row in attributes.RECOMMENDATIONS}
    order = {key: index for index, key in enumerate(statuses)}
    entries = sorted(
        shortlist.entries.select_related("profile__user", "assigned_to"),
        key=lambda entry: (order.get(entry.status, len(order)), entry.created_at),
    )
    rows = []
    for entry in entries:
        profile = entry.profile
        if access_level(profile, viewer) != "scout":
            rows.append([profile.full_name, statuses.get(entry.status, entry.status), "No longer visible to scouts", None, None, None, None, None])
            continue
        sport = _sport(profile, None)
        summary = ratings.summary(profile, organisation, sport or None)
        line = search.latest_line(profile, sport) if sport else None
        key = next(iter(_key_stats(sport, 1)), None) if sport else None
        stat = (
            f"{key['label']} {line.values[key['key']]['value']:g} (season {line.season})"
            if key and line and (line.values.get(key["key"]) or {}).get("value") is not None
            else None
        )
        top = max(summary["recommendations"], key=lambda row: row["count"])
        position = PlayerSport.objects.filter(profile=profile, sport=sport).values_list("primary_position", flat=True).first()
        rows.append(
            [
                profile.full_name,
                statuses.get(entry.status, entry.status),
                (age_group(profile.date_of_birth) or {}).get("label"),
                _position_label(sport, position) if position else None,
                stat,
                f"{summary['current_ability'] or '—'} / {summary['potential'] or '—'}",
                f"{recommendations[top['key']]} ({top['count']})" if top["count"] else None,
                entry.assigned_to.display_name if entry.assigned_to_id else None,
            ]
        )
    counts = Counter(entry.status for entry in shortlist.entries.all())
    return document(
        "shortlist",
        subtitle=f"{shortlist.name} · {shortlist.entries.count()} player(s)",
        organisation=organisation,
        sections=[
            facts(
                "Status",
                [fact(label, counts.get(key, 0)) for key, label in statuses.items()],
                note=shortlist.description,
            ),
            table(
                "Players",
                ["Player", "Status", "Age group", "Position", "Key number", "Ability / potential", "Recommendation", "Scout"],
                rows,
                note="Ability, potential and recommendation are your organisation's confidence-weighted ratings.",
            ),
        ],
        viewer=viewer,
        access="scout",
    )


# --- 5. Competition talent report ---------------------------------------------------------


def competition_report(viewer, pk, per_position: int = 5) -> dict:
    competition = scouting_leagues(viewer).filter(pk=pk).first()
    if competition is None:
        raise NotFound("No competition open to scouts found.")
    sport = catalog.sport_for_competition(competition.sport)
    if sport is None:
        raise ValidationError("This competition's sport is not in the scouting catalogue.")
    key_stats = _key_stats(sport, 4)
    lines = {
        line.user_id: line
        for line in PlayerStatLine.objects.filter(competition=competition, sport=sport)
    }
    players = []
    for user in stats.players_in_competition(competition):
        profile = PlayerProfile.objects.filter(user=user).first()
        if profile is None or access_level(profile, viewer) not in {"scout", "public"}:
            continue
        line = lines.get(user.id)
        if line is None or not line.matches:
            continue
        position = PlayerSport.objects.filter(profile=profile, sport=sport).values_list("primary_position", flat=True).first() or ""
        players.append((profile, line, position))

    # Each key stat is ranked within this competition (no minimum sample: it is this event).
    within: dict = defaultdict(dict)
    for definition in key_stats:
        values = [
            (profile.id, (line.values.get(definition["key"]) or {}).get("per_match"))
            for profile, line, _ in players
        ]
        values = [(pid, value) for pid, value in values if value is not None]
        others = len(values) - 1
        for pid, value in values:
            if not others:
                within[pid][definition["key"]] = 100.0
                continue
            beaten = sum(
                1
                for _, other in values
                if (other < value if definition["better"] == "higher" else other > value)
            )
            level = sum(1 for _, other in values if other == value) - 1
            within[pid][definition["key"]] = round((beaten + 0.5 * level) / others * 100, 1)

    by_position: dict = defaultdict(list)
    for profile, line, position in players:
        scores = list(within[profile.id].values())
        standout = round(sum(scores) / len(scores), 1) if scores else None
        by_position[position].append((standout, profile, line))

    sections: list = [
        facts(
            "Competition",
            [
                fact("Competition", competition.name),
                fact("Sport", catalog.SPORTS[sport]["label"]),
                fact("Players with stats", len(players), source=ENGINE),
                fact("Computed", max((line.computed_at for _, line, _ in players), default=None)),
            ],
            note=(
                "Standout score: the average of each key stat's per-match rank within this "
                "competition (0–100). Only players the viewer may see are included."
            ),
        )
    ]
    for position in sorted(by_position, key=lambda key: _position_label(sport, key) if key else "~"):
        ranked = sorted(by_position[position], key=lambda row: (-(row[0] or 0), row[1].full_name))[:per_position]
        sections.append(
            table(
                _position_label(sport, position) if position else "No position set",
                ["Player", "Team matches", *[f"{row['label']} / match" for row in key_stats], "Standout"],
                [
                    [
                        profile.full_name,
                        line.matches,
                        *[(line.values.get(row["key"]) or {}).get("per_match") for row in key_stats],
                        standout,
                    ]
                    for standout, profile, line in ranked
                ],
                highlight=[0] if ranked else [],
            )
        )
    organisation = _organisation(viewer)
    return document(
        "competition",
        subtitle=competition.name,
        organisation=organisation,
        sections=sections,
        viewer=viewer,
        access="scout",
    )


# --- 6. Scout activity report -------------------------------------------------------------


def activity_report(viewer, organisation_id=None, start=None, end=None) -> dict:
    organisation = _organisation(viewer, organisation_id)
    if organisation is None or not is_scout_admin_of(viewer, organisation):
        raise PermissionDenied("Only a scout admin of the organisation sees its scout activity.")
    end_on = _parse(end) or timezone.now().date()
    start_on = _parse(start) or end_on - timedelta(days=90)
    ratings_qs = ScoutRating.objects.filter(
        organisation=organisation,
        observed_at__date__gte=start_on,
        observed_at__date__lte=end_on,
    ).select_related("scout", "profile")
    per_scout: dict = defaultdict(lambda: {"ratings": 0, "players": set(), "last": None, "live": 0})
    for rating in ratings_qs:
        row = per_scout[rating.scout.display_name]
        row["ratings"] += 1
        row["players"].add(rating.profile_id)
        row["live"] += rating.watched == "live"
        row["last"] = max(filter(None, [row["last"], rating.observed_at]))
    watched = {rating.profile_id: rating.profile for rating in ratings_qs}
    shortlisted = set(
        Shortlist.objects.filter(organisation=organisation).values_list("entries__profile_id", flat=True)
    ) - {None}
    regions = Counter((profile.region or "Not set") for profile in watched.values())
    groups = Counter(((age_group(profile.date_of_birth) or {}).get("label") or "Unknown") for profile in watched.values())
    return document(
        "activity",
        subtitle=f"{organisation.name} · {start_on.isoformat()} to {end_on.isoformat()}",
        organisation=organisation,
        sections=[
            facts(
                "Summary",
                [
                    fact("Ratings", ratings_qs.count()),
                    fact("Players watched", len(watched)),
                    fact("Players on shortlists", len(shortlisted)),
                    fact("Scouts active", len(per_scout)),
                ],
            ),
            table(
                "Ratings per scout",
                ["Scout", "Ratings", "Players", "Watched live", "Last rating"],
                [
                    [name, row["ratings"], len(row["players"]), row["live"], row["last"]]
                    for name, row in sorted(per_scout.items(), key=lambda item: -item[1]["ratings"])
                ],
            ),
            table("Coverage by region", ["Region", "Players watched"], sorted(regions.items(), key=lambda item: -item[1])),
            table("Coverage by age group", ["Age group", "Players watched"], sorted(groups.items())),
        ],
        viewer=viewer,
        access="scout_admin",
    )


def build(viewer, kind: str, params) -> tuple[dict, dict]:
    """The report and what to log about it (profile, competition, other parameters)."""

    if kind == "player":
        report = player_report(viewer, params.get("profile"), params.get("sport"))
        return report, {"profile_id": params.get("profile")}
    if kind == "progress":
        report = progress_report(viewer, params.get("profile"), params.get("sport"), params.get("from"), params.get("to"))
        return report, {"profile_id": params.get("profile")}
    if kind == "compare":
        ids = [value for value in (params.get("profiles") or "").split(",") if value]
        return compare_report(viewer, ids, params.get("sport")), {"params": {"profiles": ids}}
    if kind == "shortlist":
        return shortlist_report(viewer, params.get("shortlist")), {"params": {"shortlist": params.get("shortlist")}}
    if kind == "competition":
        return competition_report(viewer, params.get("competition")), {"competition_id": params.get("competition")}
    if kind == "activity":
        report = activity_report(viewer, params.get("organisation"), params.get("from"), params.get("to"))
        return report, {"params": {"organisation": report["organisation"]["id"]}}
    raise NotFound("Unknown report.")
