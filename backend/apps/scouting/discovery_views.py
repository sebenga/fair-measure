"""Scouting Phase 5 API: talent search, saved searches, compare, shortlists, contact."""

from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import attributes, catalog, ratings, search, stats
from .models import (
    ContactRequest,
    GuardianLink,
    Organisation,
    PlayerProfile,
    SavedSearch,
    Shortlist,
    ShortlistComment,
    ShortlistEntry,
    ShortlistLog,
)
from .serializers import ProfileCardSerializer
from .services import access_level, is_minor, is_scout, scout_organisations

TAG = ["Scouting"]


def _require_scout(user) -> list[Organisation]:
    if not is_scout(user):
        raise PermissionDenied("Only scouts use talent search, shortlists and contact.")
    return scout_organisations(user)


def _row(item: dict) -> dict:
    return {**ProfileCardSerializer(item["profile"]).data, "facts": item["facts"]}


# --- Search ------------------------------------------------------------------------------


class SearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Talent search",
        description=(
            "Body: {filters: {...}}. Filters: q, sport, position, age_group, gender, region, "
            "level (minimum competition level), has_video, tests [{key, op, value}], stats "
            "[{key, op, value}], percentiles [{key, min}], areas [{key, min}], potential_min, "
            "current_min, recommendation. op is lt, lte, gt, gte or eq. Ratings filters use your "
            "organisation's ratings. Private profiles and under-18s without guardian consent "
            "never appear."
        ),
        request=dict,
        responses=dict,
    )
    def post(self, request: Request) -> Response:
        _require_scout(request.user)
        rows = search.run(request.user, request.data.get("filters") or {})
        return Response({"count": len(rows), "results": [_row(item) for item in rows]})


def _saved_row(row: SavedSearch) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "filters": row.filters,
        "alerts": row.alerts,
        "matches": len(row.matched_ids),
        "last_run_at": row.last_run_at,
        "created_at": row.created_at,
    }


class SavedSearchListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="My saved searches", responses=dict)
    def get(self, request: Request) -> Response:
        _require_scout(request.user)
        return Response([_saved_row(row) for row in SavedSearch.objects.filter(user=request.user)])

    @extend_schema(
        tags=TAG,
        summary="Save a search; with alerts on, new matches are notified (push and in-app)",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request) -> Response:
        organisations = _require_scout(request.user)
        name = str(request.data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "Name the search."})
        filters = search.clean(request.data.get("filters") or {})
        current = [str(item["profile"].id) for item in search.run(request.user, filters)]
        row = SavedSearch.objects.create(
            user=request.user,
            organisation=organisations[0] if organisations else None,
            name=name[:120],
            filters=filters,
            alerts=bool(request.data.get("alerts", True)),
            matched_ids=current,
            last_run_at=timezone.now(),
        )
        return Response(_saved_row(row), status=status.HTTP_201_CREATED)


class SavedSearchDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _row(self, request, pk) -> SavedSearch:
        return get_object_or_404(SavedSearch, pk=pk, user=request.user)

    @extend_schema(
        tags=TAG,
        summary="Rename a saved search or turn its alerts on or off",
        request=dict,
        responses=dict,
    )
    def patch(self, request: Request, pk) -> Response:
        row = self._row(request, pk)
        if "name" in request.data:
            row.name = str(request.data["name"] or row.name).strip()[:120]
        if "alerts" in request.data:
            row.alerts = bool(request.data["alerts"])
        if "filters" in request.data:
            row.filters = search.clean(request.data["filters"] or {})
            row.matched_ids = [
                str(item["profile"].id) for item in search.run(request.user, row.filters)
            ]
        row.save()
        return Response(_saved_row(row))

    @extend_schema(tags=TAG, summary="Delete a saved search", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        self._row(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def run_saved_search_alerts() -> int:
    """The scheduled job: notify scouts of players newly matching their saved searches."""

    from apps.notifications.services import notify_users

    sent = 0
    for row in SavedSearch.objects.filter(alerts=True).select_related("user"):
        if not row.user.is_active or not is_scout(row.user):
            continue
        try:
            matches = search.run(row.user, row.filters)
        except ValidationError:
            continue
        ids = [str(item["profile"].id) for item in matches]
        new = [
            item["profile"]
            for item in matches
            if str(item["profile"].id) not in set(row.matched_ids)
        ]
        if new:
            names = ", ".join(profile.full_name for profile in new[:3])
            more = f" and {len(new) - 3} more" if len(new) > 3 else ""
            notify_users(
                [row.user],
                kind="scouting.search_match",
                title=f'New match for "{row.name}"',
                body=f"{names}{more} now match your saved search.",
                category="feed_activity",
                data={
                    "saved_search_id": str(row.id),
                    "profile_ids": [str(profile.id) for profile in new],
                },
            )
            sent += 1
        row.matched_ids = ids
        row.last_run_at = timezone.now()
        row.save(update_fields=["matched_ids", "last_run_at", "updated_at"])
    return sent


# --- Compare -----------------------------------------------------------------------------


KEY_STATS = 6


class CompareView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Compare 2 to 4 players: areas (your organisation's ratings), stats and tests",
        parameters=[
            OpenApiParameter("profiles", str, description="Comma-separated profile ids (2 to 4)"),
            OpenApiParameter("sport", str, description="Sport to compare in"),
        ],
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        organisations = _require_scout(request.user)
        ids = [value for value in (request.query_params.get("profiles") or "").split(",") if value]
        if not 2 <= len(set(ids)) <= 4:
            raise ValidationError({"profiles": "Compare 2 to 4 players."})
        profiles = []
        for pk in dict.fromkeys(ids):
            profile = PlayerProfile.objects.filter(pk=pk).first()
            if profile is None or access_level(profile, request.user) != "scout":
                raise NotFound("One of those players is not visible to you.")
            profiles.append(profile)
        sport = request.query_params.get("sport") or next(
            (row.sport for row in profiles[0].sports.all() if row.sport in catalog.SPORTS), ""
        )
        entry = catalog.sport_catalogue(sport)
        if entry is None:
            raise ValidationError({"sport": "Choose a sport from the catalogue."})
        stat_rows = [row for row in entry["match_stats"] if row.get("better")][:KEY_STATS]
        players = []
        for profile in profiles:
            line = search.latest_line(profile, sport)
            peers = stats.cohort(profile, sport)
            ranks = (
                stats.stat_percentiles(profile, sport, line.season, line.values, peers)
                if line
                else {}
            )
            summary = ratings.summary(profile, organisations[0], sport) if organisations else None
            players.append(
                {
                    **ProfileCardSerializer(profile).data,
                    "areas": {row["key"]: row["average"] for row in summary["areas"]}
                    if summary
                    else {},
                    "current_ability": summary["current_ability"] if summary else None,
                    "potential": summary["potential"] if summary else None,
                    "season": line.season if line else None,
                    "matches": line.matches if line else 0,
                    "stats": {
                        row["key"]: {
                            "value": ((line.values if line else {}).get(row["key"]) or {}).get(
                                "value"
                            ),
                            "percentile": (ranks.get(row["key"]) or {}).get("percentile"),
                        }
                        for row in stat_rows
                    },
                    "tests": {
                        row["key"]: {
                            "best": row["personal_best"]["value"],
                            "verified": row["personal_best"]["verified"],
                            "percentile": row["percentile"],
                        }
                        for row in stats.test_summary(profile, sport, peers)
                    },
                }
            )
        return Response(
            {
                "sport": sport,
                "areas": [
                    {"key": area["key"], "label": area["label"]} for area in attributes.AREAS
                ],
                "stats": [
                    {
                        "key": row["key"],
                        "label": row["label"],
                        "unit": row.get("unit", ""),
                        "better": row["better"],
                    }
                    for row in stat_rows
                ],
                "tests": [
                    {
                        "key": row["key"],
                        "label": row["label"],
                        "unit": row["unit"],
                        "better": row["better"],
                    }
                    for row in entry["physical_tests"]
                ],
                "players": players,
            }
        )


# --- Shortlists --------------------------------------------------------------------------


def _organisation(request: Request, organisation_id=None) -> Organisation:
    mine = _require_scout(request.user)
    if not mine:
        raise PermissionDenied("Join a scouting organisation to use shortlists.")
    if organisation_id:
        found = next((row for row in mine if str(row.id) == str(organisation_id)), None)
        if found is None:
            raise PermissionDenied("You do not scout for that organisation.")
        return found
    return mine[0]


def _shortlist(request: Request, pk) -> Shortlist:
    mine = {row.id for row in _require_scout(request.user)}
    row = get_object_or_404(Shortlist, pk=pk)
    if row.organisation_id not in mine:
        raise NotFound("No shortlist found.")
    return row


def _log(shortlist, profile, actor, action, before=None, after=None) -> None:
    ShortlistLog.objects.create(
        shortlist=shortlist,
        profile=profile,
        actor=actor,
        action=action,
        before=before or {},
        after=after or {},
    )


def _person(user) -> dict | None:
    return {"id": str(user.id), "name": user.display_name} if user else None


def _latest_contact(entry: ShortlistEntry) -> dict | None:
    row = (
        ContactRequest.objects.filter(
            profile=entry.profile, organisation=entry.shortlist.organisation
        )
        .order_by("-created_at")
        .first()
    )
    return {"status": row.status, "created_at": row.created_at} if row else None


def _entry_row(entry: ShortlistEntry) -> dict:
    return {
        "id": str(entry.id),
        "profile": ProfileCardSerializer(entry.profile).data,
        "status": entry.status,
        "assigned_to": _person(entry.assigned_to),
        "added_by": _person(entry.added_by),
        "created_at": entry.created_at,
        "comments": [
            {
                "id": str(row.id),
                "author": _person(row.author),
                "body": row.body,
                "created_at": row.created_at,
            }
            for row in entry.comments.select_related("author")
        ],
        "contact": _latest_contact(entry),
    }


def _shortlist_row(row: Shortlist, *, entries: bool = False) -> dict:
    data = {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "organisation": {"id": str(row.organisation_id), "name": row.organisation.name},
        "count": row.entries.count(),
        "statuses": {
            item["key"]: row.entries.filter(status=item["key"]).count()
            for item in attributes.SHORTLIST_STATUSES
        },
        "created_at": row.created_at,
    }
    if entries:
        data["entries"] = [
            _entry_row(entry)
            for entry in row.entries.select_related(
                "profile__user", "assigned_to", "added_by", "shortlist__organisation"
            )
        ]
        data["scouts"] = [
            _person(role.user)
            for role in row.organisation.roles.filter(
                role__in=["scout", "scout_admin"]
            ).select_related("user")
        ]
    return data


class ShortlistListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="My organisations' shortlists", responses=dict)
    def get(self, request: Request) -> Response:
        mine = _require_scout(request.user)
        rows = Shortlist.objects.filter(organisation__in=mine).select_related("organisation")
        profile = request.query_params.get("profile")
        data = [_shortlist_row(row) for row in rows]
        if profile:
            on = set(
                ShortlistEntry.objects.filter(shortlist__in=rows, profile_id=profile).values_list(
                    "shortlist_id", flat=True
                )
            )
            for row in data:
                row["has_profile"] = row["id"] in {str(value) for value in on}
        return Response(data)

    @extend_schema(
        tags=TAG,
        summary="Create a shortlist for my organisation",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request) -> Response:
        organisation = _organisation(request, request.data.get("organisation"))
        name = str(request.data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "Name the shortlist."})
        if Shortlist.objects.filter(organisation=organisation, name__iexact=name).exists():
            raise ValidationError(
                {"name": "Your organisation already has a shortlist with that name."}
            )
        row = Shortlist.objects.create(
            organisation=organisation,
            name=name[:120],
            description=str(request.data.get("description") or "")[:280],
            created_by=request.user,
        )
        return Response(_shortlist_row(row, entries=True), status=status.HTTP_201_CREATED)


class ShortlistDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="A shortlist with its players, comments and scouts", responses=dict
    )
    def get(self, request: Request, pk) -> Response:
        return Response(_shortlist_row(_shortlist(request, pk), entries=True))

    @extend_schema(tags=TAG, summary="Delete a shortlist", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        _shortlist(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShortlistEntriesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Add a player to a shortlist", request=dict, responses={201: dict}
    )
    def post(self, request: Request, pk) -> Response:
        shortlist = _shortlist(request, pk)
        profile = PlayerProfile.objects.filter(pk=request.data.get("profile")).first()
        if profile is None or access_level(profile, request.user) != "scout":
            raise ValidationError({"profile": "That player is not visible to scouts."})
        entry, created = ShortlistEntry.objects.get_or_create(
            shortlist=shortlist, profile=profile, defaults={"added_by": request.user}
        )
        if not created:
            raise ValidationError({"profile": "That player is already on this shortlist."})
        _log(
            shortlist,
            profile,
            request.user,
            ShortlistLog.Action.ADDED,
            after={"status": entry.status},
        )
        return Response(_entry_row(entry), status=status.HTTP_201_CREATED)


class ShortlistEntryDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _entry(self, request, pk, entry_id) -> ShortlistEntry:
        shortlist = _shortlist(request, pk)
        return get_object_or_404(ShortlistEntry, pk=entry_id, shortlist=shortlist)

    @extend_schema(
        tags=TAG, summary="Change a player's status or assigned scout", request=dict, responses=dict
    )
    def patch(self, request: Request, pk, entry_id) -> Response:
        entry = self._entry(request, pk, entry_id)
        with transaction.atomic():
            if "status" in request.data:
                wanted = str(request.data["status"])
                if wanted not in ShortlistEntry.Status.values:
                    raise ValidationError(
                        {"status": "Choose Watching, Contacted, Trial booked, Signed or Rejected."}
                    )
                if wanted != entry.status:
                    _log(
                        entry.shortlist,
                        entry.profile,
                        request.user,
                        ShortlistLog.Action.STATUS,
                        {"status": entry.status},
                        {"status": wanted},
                    )
                    entry.status = wanted
            if "assigned_to" in request.data:
                wanted = request.data["assigned_to"] or None
                person = None
                if wanted:
                    role = (
                        entry.shortlist.organisation.roles.filter(
                            user_id=wanted, role__in=["scout", "scout_admin"]
                        )
                        .select_related("user")
                        .first()
                    )
                    if role is None:
                        raise ValidationError(
                            {"assigned_to": "Assign a scout from your organisation."}
                        )
                    person = role.user
                if (person.id if person else None) != entry.assigned_to_id:
                    _log(
                        entry.shortlist,
                        entry.profile,
                        request.user,
                        ShortlistLog.Action.ASSIGNED,
                        {"assigned_to": _person(entry.assigned_to)},
                        {"assigned_to": _person(person)},
                    )
                    entry.assigned_to = person
            entry.save()
        return Response(_entry_row(entry))

    @extend_schema(tags=TAG, summary="Remove a player from a shortlist", responses={204: None})
    def delete(self, request: Request, pk, entry_id) -> Response:
        entry = self._entry(request, pk, entry_id)
        _log(
            entry.shortlist,
            entry.profile,
            request.user,
            ShortlistLog.Action.REMOVED,
            before={"status": entry.status},
        )
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShortlistCommentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Comment on a shortlisted player", request=dict, responses={201: dict}
    )
    def post(self, request: Request, pk, entry_id) -> Response:
        shortlist = _shortlist(request, pk)
        entry = get_object_or_404(ShortlistEntry, pk=entry_id, shortlist=shortlist)
        body = str(request.data.get("body") or "").strip()
        if not body:
            raise ValidationError({"body": "Write a comment."})
        comment = ShortlistComment.objects.create(
            entry=entry, author=request.user, body=body[:2000]
        )
        _log(
            shortlist,
            entry.profile,
            request.user,
            ShortlistLog.Action.COMMENTED,
            after={"comment": comment.body[:200]},
        )
        return Response(_entry_row(entry), status=status.HTTP_201_CREATED)


class ShortlistLogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Every change to a shortlist", responses=dict)
    def get(self, request: Request, pk) -> Response:
        shortlist = _shortlist(request, pk)
        return Response(
            [
                {
                    "id": str(row.id),
                    "action": row.action,
                    "action_label": row.get_action_display(),
                    "player": row.profile.full_name,
                    "actor": _person(row.actor),
                    "before": row.before,
                    "after": row.after,
                    "created_at": row.created_at,
                }
                for row in shortlist.log.select_related("profile", "actor")[:200]
            ]
        )


# --- Contact requests -----------------------------------------------------------------------


def _recipients(profile: PlayerProfile) -> list:
    """Who answers: the player, or their active guardians when under 18."""

    if is_minor(profile):
        return [
            link.guardian
            for link in GuardianLink.objects.filter(
                profile=profile, status=GuardianLink.Status.ACTIVE
            ).select_related("guardian")
            if link.guardian_id
        ]
    return [profile.user]


def _contact_row(row: ContactRequest, viewer) -> dict:
    return {
        "id": str(row.id),
        "player": {"id": str(row.profile_id), "name": row.profile.full_name},
        "organisation": {"id": str(row.organisation_id), "name": row.organisation.name},
        "requested_by": _person(row.requested_by),
        "message": row.message,
        "to_guardian": row.to_guardian,
        "status": row.status,
        "status_label": row.get_status_display(),
        "response": row.response,
        "responded_at": row.responded_at,
        "created_at": row.created_at,
        "can_respond": row.status == ContactRequest.Status.PENDING
        and viewer in _recipients(row.profile),
    }


class ContactRequestCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Ask to get in touch with a player (their guardian answers for under-18s)",
        description="The platform never shares phone numbers or email addresses.",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        from apps.notifications.services import notify_users

        organisation = _organisation(request, request.data.get("organisation"))
        profile = get_object_or_404(PlayerProfile, pk=pk)
        if access_level(profile, request.user) != "scout":
            raise NotFound("No profile found.")
        message = str(request.data.get("message") or "").strip()
        if len(message) < 10:
            raise ValidationError({"message": "Say who you are and why you would like to talk."})
        if ContactRequest.objects.filter(
            profile=profile, organisation=organisation, status=ContactRequest.Status.PENDING
        ).exists():
            raise ValidationError(
                {"message": "Your organisation is already waiting for an answer from this player."}
            )
        recipients = _recipients(profile)
        if not recipients:
            raise ValidationError({"profile": "This player has no active guardian to answer yet."})
        minor = is_minor(profile)
        row = ContactRequest.objects.create(
            profile=profile,
            organisation=organisation,
            requested_by=request.user,
            message=message[:2000],
            to_guardian=minor,
        )
        title = f"{organisation.name} would like to get in touch"
        body = (
            f"About {profile.first_name}. Answer in the app; your contact details stay private."
            if minor
            else ("Answer in the app; your contact details stay private.")
        )
        notify_users(
            recipients,
            kind="scouting.contact_request",
            title=title,
            body=body,
            category="announcements",
            data={"contact_request_id": str(row.id)},
        )
        for entry in ShortlistEntry.objects.filter(
            shortlist__organisation=organisation, profile=profile
        ).select_related("shortlist"):
            _log(
                entry.shortlist,
                profile,
                request.user,
                ShortlistLog.Action.CONTACTED,
                after={"to_guardian": minor},
            )
            if entry.status == ShortlistEntry.Status.WATCHING:
                _log(
                    entry.shortlist,
                    profile,
                    request.user,
                    ShortlistLog.Action.STATUS,
                    {"status": entry.status},
                    {"status": "contacted"},
                )
                entry.status = ShortlistEntry.Status.CONTACTED
                entry.save(update_fields=["status", "updated_at"])
        return Response(_contact_row(row, request.user), status=status.HTTP_201_CREATED)


class ContactRequestListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Contact requests: received (as player or guardian) or sent (my organisations)",
        parameters=[OpenApiParameter("box", str, description="received (default) or sent")],
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        if request.query_params.get("box") == "sent":
            mine = _require_scout(request.user)
            rows = ContactRequest.objects.filter(organisation__in=mine)
        else:
            guarded = GuardianLink.objects.filter(
                guardian=request.user, status=GuardianLink.Status.ACTIVE
            ).values_list("profile_id", flat=True)
            rows = ContactRequest.objects.filter(
                profile_id__in=list(guarded), to_guardian=True
            ) | ContactRequest.objects.filter(profile__user=request.user, to_guardian=False)
        rows = rows.select_related("profile", "organisation", "requested_by").order_by(
            "-created_at"
        )
        return Response([_contact_row(row, request.user) for row in rows[:100]])


class ContactRequestRespondView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Accept or decline a contact request", request=dict, responses=dict
    )
    def post(self, request: Request, pk) -> Response:
        from apps.notifications.services import notify_users

        row = get_object_or_404(
            ContactRequest.objects.select_related("profile", "organisation"), pk=pk
        )
        if request.user not in _recipients(row.profile):
            raise PermissionDenied(
                "A parent or guardian answers for players under 18."
                if row.to_guardian
                else "Only the player can answer."
            )
        if row.status != ContactRequest.Status.PENDING:
            raise ValidationError("This request was already answered.")
        accept = bool(request.data.get("accept"))
        row.status = ContactRequest.Status.ACCEPTED if accept else ContactRequest.Status.DECLINED
        row.response = str(request.data.get("message") or "")[:2000]
        row.responded_by = request.user
        row.responded_at = timezone.now()
        row.save()
        notify_users(
            [row.requested_by],
            kind="scouting.contact_answer",
            title=f"{row.profile.full_name}: {'accepted' if accept else 'declined'}",
            body=row.response[:300]
            or ("They are happy to talk through the app." if accept else "Not this time."),
            category="announcements",
            data={"contact_request_id": str(row.id)},
        )
        return Response(_contact_row(row, request.user))


class ContactRequestWithdrawView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Withdraw a contact request my organisation sent", responses=dict
    )
    def post(self, request: Request, pk) -> Response:
        mine = {row.id for row in _require_scout(request.user)}
        row = get_object_or_404(ContactRequest, pk=pk, organisation_id__in=mine)
        if row.status != ContactRequest.Status.PENDING:
            raise ValidationError("Only a waiting request can be withdrawn.")
        row.status = ContactRequest.Status.WITHDRAWN
        row.save(update_fields=["status", "updated_at"])
        return Response(_contact_row(row, request.user))
