"""Games reports: the final medal table, a results book per sport, an NOC summary
and the daily results. Each report is one shape — a title and sections of rows —
so the CSV export and the printable (PDF) page are built from the same data."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

from django.utils import timezone

from .experience import event_label, event_rounds, noc_page, points_table, record_row
from .models import NOC, Games, Medal

KINDS = ("medal-table", "results-book", "noc-summary", "daily")
MEDAL_COLUMNS = ["Rank", "Code", "Name", "Gold", "Silver", "Bronze", "Total"]
RESULT_COLUMNS = ["Rank", "Entrant", "Code", "Mark", "Status", "Qualified"]


def _section(heading: str, columns: list[str], rows: list[list]) -> dict:
    return {
        "heading": heading,
        "columns": columns,
        "rows": [[_cell(value) for value in row] for row in rows],
    }


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value)


def medal_table_report(games: Games) -> dict:
    from .services import medal_table

    sections = [
        _section(
            "Medal table",
            MEDAL_COLUMNS,
            [
                [
                    row["rank"],
                    row["code"],
                    row["name"],
                    row["gold"],
                    row["silver"],
                    row["bronze"],
                    row["total"],
                ]
                for row in medal_table(games)
            ],
        )
    ]
    if games.placing_points:
        scale = ", ".join(str(value) for value in games.placing_points)
        sections.append(
            _section(
                f"Points table (placing points {scale})",
                ["Rank", "Code", "Name", "Points", "Placings", "Gold", "Silver", "Bronze"],
                [
                    [
                        row["rank"],
                        row["code"],
                        row["name"],
                        row["points"],
                        row["placings"],
                        row["gold"],
                        row["silver"],
                        row["bronze"],
                    ]
                    for row in points_table(games)
                ],
            )
        )
    ranking = (
        "golds first"
        if games.medal_table_ranking == Games.Ranking.GOLD_FIRST
        else "total medals first"
    )
    return {
        "title": f"{games.name}: medal table",
        "subtitle": f"Ranked by {ranking}",
        "sections": sections,
    }


def results_book(games: Games, sport_key: str | None) -> dict:
    events = games.events.select_related("competition").order_by(
        "sport_label", "display_order", "name"
    )
    if sport_key:
        events = events.filter(sport_key=sport_key)
    sections = []
    sport_label = ""
    for event in events:
        sport_label = event.sport_label
        medals = event.medals.select_related("noc", "entry__participant").order_by("rank")
        if medals:
            sections.append(
                _section(
                    f"{event_label(event)} · medals",
                    ["Medal", "Entrant", "Code"],
                    [
                        [medal.get_medal_display(), medal.entry.participant.name, medal.noc.code]
                        for medal in medals
                    ],
                )
            )
        for round_row in event_rounds(event):
            sections.append(
                _section(
                    f"{event_label(event)} · {round_row['label']}",
                    RESULT_COLUMNS,
                    [
                        [
                            row["rank"],
                            row["name"],
                            row["noc"],
                            row["mark"],
                            row["status"],
                            row["qualified"],
                        ]
                        for row in round_row["results"]
                    ],
                )
            )
    title = f"{games.name}: results book" + (
        f" · {sport_label}" if sport_key and sport_label else ""
    )
    return {"title": title, "subtitle": f"{events.count()} event(s)", "sections": sections}


def noc_summary(games: Games, noc: NOC) -> dict:
    page = noc_page(noc)
    return {
        "title": f"{games.name}: {noc.code} {noc.name}",
        "subtitle": f"{len(page['athletes'])} athlete(s) · {len(page['medals'])} medal(s)",
        "sections": [
            _section(
                "Medals by sport",
                ["Sport", "Gold", "Silver", "Bronze"],
                [
                    [row["sport"], row["gold"], row["silver"], row["bronze"]]
                    for row in page["medals_by_sport"]
                ],
            ),
            _section(
                "Medals",
                ["Event", "Medal", "Entrant"],
                [[row["event"], row["medal"].title(), row["entrant"]] for row in page["medals"]],
            ),
            _section(
                "Results",
                ["Event", "Round", "Rank", "Mark", "Status", "Qualified"],
                [
                    [
                        row["event"],
                        row["round"],
                        row["rank"],
                        row["mark"],
                        row["status"],
                        row["qualified"],
                    ]
                    for row in page["results"]
                ],
            ),
            _section(
                "Athletes",
                ["Athlete", "Events"],
                [[row["name"], row["events"]] for row in page["athletes"]],
            ),
        ],
    }


def daily_results(games: Games, day: date) -> dict:
    from apps.fixtures.models import Fixture

    start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
    end = start + timedelta(days=1)
    events = {event.competition_id: event for event in games.events.select_related("competition")}
    medals = (
        Medal.objects.filter(event__games=games, created_at__gte=start, created_at__lt=end)
        .select_related("event", "noc", "entry__participant")
        .order_by("event__sport_label", "event__name", "rank")
    )
    by_event: dict = {}
    for medal in medals:
        row = by_event.setdefault(
            medal.event_id,
            {"event": event_label(medal.event), "gold": [], "silver": [], "bronze": []},
        )
        row[medal.medal].append(medal.entry.participant.name)
    sections = [
        _section(
            "Medals awarded",
            ["Event", "Gold", "Silver", "Bronze"],
            [
                [
                    row["event"],
                    "; ".join(row["gold"]),
                    "; ".join(row["silver"]),
                    "; ".join(row["bronze"]),
                ]
                for row in by_event.values()
            ],
        )
    ]
    finished = Fixture.objects.filter(
        competition_id__in=events,
        status__in=[Fixture.Status.COMPLETED, Fixture.Status.FORFEIT],
        completed_at__gte=start,
        completed_at__lt=end,
    ).order_by("completed_at")
    seen = set()
    for fixture in finished:
        event = events[fixture.competition_id]
        for round_row in event_rounds(event):
            if round_row["fixture_id"] != str(fixture.id) or fixture.id in seen:
                continue
            seen.add(fixture.id)
            sections.append(
                _section(
                    f"{event_label(event)} · {round_row['label']}",
                    RESULT_COLUMNS,
                    [
                        [
                            row["rank"],
                            row["name"],
                            row["noc"],
                            row["mark"],
                            row["status"],
                            row["qualified"],
                        ]
                        for row in round_row["results"]
                    ],
                )
            )
    records = games.records.filter(set_on=day).select_related("event", "noc")
    sections.append(
        _section(
            "Records",
            ["Event", "Record", "Mark", "Holder", "Code", "Previous"],
            [
                [
                    row["event"],
                    row["scope_label"],
                    row["mark"],
                    row["holder"],
                    row["noc"],
                    row["previous_mark"],
                ]
                for row in map(record_row, records)
            ],
        )
    )
    return {
        "title": f"{games.name}: daily results",
        "subtitle": day.strftime("%A %d %B %Y"),
        "sections": sections,
    }


def build(games: Games, kind: str, params) -> dict:
    from rest_framework.exceptions import NotFound, ValidationError

    if kind == "medal-table":
        return medal_table_report(games)
    if kind == "results-book":
        return results_book(games, params.get("sport") or None)
    if kind == "noc-summary":
        noc = games.nocs.filter(pk=params.get("noc")).first() if params.get("noc") else None
        if noc is None:
            raise ValidationError({"noc": "Choose the NOC for the summary."})
        return noc_summary(games, noc)
    if kind == "daily":
        try:
            day = (
                date.fromisoformat(params.get("date"))
                if params.get("date")
                else timezone.localdate()
            )
        except ValueError as error:
            raise ValidationError({"date": "Use a date like 2026-07-28."}) from error
        return daily_results(games, day)
    raise NotFound("Unknown report.")


def to_csv(report: dict) -> str:
    """One CSV: the title, then each section's heading, columns and rows, blank-line separated."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([report["title"]])
    if report.get("subtitle"):
        writer.writerow([report["subtitle"]])
    for section in report["sections"]:
        writer.writerow([])
        writer.writerow([section["heading"]])
        writer.writerow(section["columns"])
        writer.writerows(section["rows"])
    return buffer.getvalue()
