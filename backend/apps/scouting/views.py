"""Scouting API: player profiles, guardian consent, organisations and roles."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import Role, has_at_least

from . import catalog
from .models import (
    ConsentRecord,
    GuardianLink,
    HighlightVideo,
    InjuryRecord,
    Measurement,
    Organisation,
    PlayerProfile,
    PlayerSport,
    ScoutingRole,
)
from .serializers import (
    CoachRoleSerializer,
    ConsentDecisionSerializer,
    ConsentRecordSerializer,
    GuardianInviteSerializer,
    GuardianLinkSerializer,
    HighlightVideoSerializer,
    InjurySerializer,
    MeasurementSerializer,
    OrganisationMemberWriteSerializer,
    OrganisationSerializer,
    PlayerProfileSerializer,
    PlayerSportSerializer,
    ProfileCardSerializer,
    ScoutingRoleSerializer,
    ScoutProfileSerializer,
)
from .services import (
    access_level,
    coaches_player,
    effective_visibility,
    grant_role,
    is_scout_admin_of,
    record_consent,
    roles_of,
    team_payload,
    visible_profiles,
)

User = get_user_model()
TAG = ["Scouting"]


def _my_profile(user) -> PlayerProfile:
    profile = PlayerProfile.objects.filter(user=user).first()
    if profile is None:
        raise NotFound("You have not created a player profile yet.")
    return profile


def _full(profile: PlayerProfile, request: Request, access: str = "owner") -> dict:
    profile = PlayerProfile.objects.prefetch_related(
        "sports", "measurements", "injuries", "videos", "guardians", "teams__competition"
    ).get(pk=profile.pk)
    return PlayerProfileSerializer(profile, context={"request": request, "access": access}).data


# --- Catalogue and "me" ------------------------------------------------------


class CatalogView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG,
        summary="Sports, positions, rating areas, age groups and consent sections",
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        return Response(catalog.public_catalog())


class CatalogSportView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG,
        summary="One sport's rating catalogue: areas, attributes, physical tests, match stats",
        description=(
            "Every sport rates the same five areas (physical, technical, tactical, mental, "
            "context) from 1 to 10. Attributes may apply only to some positions. Each match "
            "stat names its engine source (a score type key or an outcome/result value) or a "
            "formula over the sport's other stats."
        ),
        responses=dict,
    )
    def get(self, request: Request, sport: str) -> Response:
        payload = catalog.sport_catalogue(sport)
        if payload is None:
            raise NotFound("That sport is not in the scouting catalogue.")
        return Response(payload)


class ScoutingMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="My scouting roles, organisations and pending guardian requests",
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        user = request.user
        profile = PlayerProfile.objects.filter(user=user).first()
        pending = GuardianLink.objects.filter(
            invited_email__iexact=user.email, status=GuardianLink.Status.PENDING
        ).count()
        roles = ScoutingRole.objects.filter(user=user).select_related("organisation", "team")
        organisations = Organisation.objects.filter(roles__user=user).distinct()
        return Response(
            {
                "roles": ScoutingRoleSerializer(roles, many=True).data,
                "role_keys": sorted(roles_of(user)),
                "organisations": OrganisationSerializer(
                    organisations, many=True, context={"request": request}
                ).data,
                "profile_id": str(profile.id) if profile else None,
                "guarding": GuardianLink.objects.filter(
                    guardian=user, status=GuardianLink.Status.ACTIVE
                ).count(),
                "pending_guardian_requests": pending,
            }
        )


# --- My player profile -------------------------------------------------------


class MyProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="My player profile", responses=PlayerProfileSerializer)
    def get(self, request: Request) -> Response:
        return Response(_full(_my_profile(request.user), request))

    @extend_schema(
        tags=TAG,
        summary="Create my player profile (makes me a player)",
        request=PlayerProfileSerializer,
        responses={201: PlayerProfileSerializer},
    )
    @transaction.atomic
    def post(self, request: Request) -> Response:
        if PlayerProfile.objects.filter(user=request.user).exists():
            raise ValidationError("You already have a player profile. Edit it instead.")
        serializer = PlayerProfileSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(user=request.user)
        grant_role(request.user, ScoutingRole.Role.PLAYER)
        self._audit_visibility(profile, request.user, None)
        return Response(_full(profile, request), status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=TAG,
        summary="Update my player profile, including who can see it",
        request=PlayerProfileSerializer,
        responses=PlayerProfileSerializer,
    )
    @transaction.atomic
    def patch(self, request: Request) -> Response:
        profile = _my_profile(request.user)
        before = profile.visibility
        serializer = PlayerProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        self._audit_visibility(profile, request.user, before)
        return Response(_full(profile, request))

    @staticmethod
    def _audit_visibility(profile: PlayerProfile, user, before: str | None) -> None:
        if before == profile.visibility:
            return
        if before is None and profile.visibility == PlayerProfile.Visibility.PRIVATE:
            return
        revoked = profile.visibility == PlayerProfile.Visibility.PRIVATE
        record_consent(
            profile,
            by=user,
            given_as="player",
            action=ConsentRecord.Action.REVOKED if revoked else ConsentRecord.Action.GRANTED,
            visibility=profile.visibility,
            sections=[] if revoked else sorted(catalog.keys(catalog.CONSENT_SECTIONS)),
            note=f"Visibility changed from {before or 'new'} to {profile.visibility}.",
        )


class _OwnedRowsView(APIView):
    """Create rows on my profile, and update or delete one by id."""

    permission_classes = [permissions.IsAuthenticated]
    model = None
    serializer_class = None

    def _row(self, request: Request, pk):
        return get_object_or_404(self.model, pk=pk, profile__user=request.user)

    def _create(self, request: Request) -> Response:
        profile = _my_profile(request.user)
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.save_new(serializer, profile, request)
        return Response(_full(profile, request), status=status.HTTP_201_CREATED)

    def save_new(self, serializer, profile, request) -> None:
        serializer.save(profile=profile)


class MySportsView(_OwnedRowsView):
    model = PlayerSport
    serializer_class = PlayerSportSerializer

    @extend_schema(
        tags=TAG,
        summary="Add a sport and positions",
        request=PlayerSportSerializer,
        responses={201: PlayerProfileSerializer},
    )
    def post(self, request: Request) -> Response:
        profile = _my_profile(request.user)
        if profile.sports.filter(sport=request.data.get("sport")).exists():
            raise ValidationError({"sport": "That sport is already on your profile."})
        return self._create(request)

    def save_new(self, serializer, profile, request) -> None:
        first = not profile.sports.exists()
        row = serializer.save(
            profile=profile, is_primary=first or serializer.validated_data.get("is_primary", False)
        )
        if row.is_primary:
            profile.sports.exclude(pk=row.pk).update(is_primary=False)


class MySportDetailView(_OwnedRowsView):
    model = PlayerSport
    serializer_class = PlayerSportSerializer

    @extend_schema(
        tags=TAG,
        summary="Change a sport's positions",
        request=PlayerSportSerializer,
        responses=PlayerProfileSerializer,
    )
    def patch(self, request: Request, pk) -> Response:
        row = self._row(request, pk)
        data = {**request.data, "sport": row.sport}
        serializer = PlayerSportSerializer(row, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        if row.is_primary:
            row.profile.sports.exclude(pk=row.pk).update(is_primary=False)
        return Response(_full(row.profile, request))

    @extend_schema(tags=TAG, summary="Remove a sport", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        self._row(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyMeasurementsView(_OwnedRowsView):
    model = Measurement
    serializer_class = MeasurementSerializer

    @extend_schema(
        tags=TAG,
        summary="Add a self-reported measurement",
        request=MeasurementSerializer,
        responses={201: PlayerProfileSerializer},
    )
    def post(self, request: Request) -> Response:
        return self._create(request)

    def save_new(self, serializer, profile, request) -> None:
        serializer.save(profile=profile, source=Measurement.Source.SELF, recorded_by=request.user)


class MyMeasurementDetailView(_OwnedRowsView):
    model = Measurement
    serializer_class = MeasurementSerializer

    @extend_schema(
        tags=TAG, summary="Delete one of my self-reported measurements", responses={204: None}
    )
    def delete(self, request: Request, pk) -> Response:
        row = self._row(request, pk)
        if row.source != Measurement.Source.SELF:
            raise PermissionDenied(
                "A verified measurement can only be removed by whoever verified it."
            )
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyInjuriesView(_OwnedRowsView):
    model = InjuryRecord
    serializer_class = InjurySerializer

    @extend_schema(
        tags=TAG,
        summary="Add an injury (private unless shared)",
        request=InjurySerializer,
        responses={201: PlayerProfileSerializer},
    )
    def post(self, request: Request) -> Response:
        return self._create(request)


class MyInjuryDetailView(_OwnedRowsView):
    model = InjuryRecord
    serializer_class = InjurySerializer

    @extend_schema(
        tags=TAG,
        summary="Update an injury or who sees it",
        request=InjurySerializer,
        responses=PlayerProfileSerializer,
    )
    def patch(self, request: Request, pk) -> Response:
        row = self._row(request, pk)
        serializer = InjurySerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_full(row.profile, request))

    @extend_schema(tags=TAG, summary="Delete an injury", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        self._row(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyVideosView(_OwnedRowsView):
    model = HighlightVideo
    serializer_class = HighlightVideoSerializer

    @extend_schema(
        tags=TAG,
        summary="Add a highlight video link or uploaded video",
        request=HighlightVideoSerializer,
        responses={201: PlayerProfileSerializer},
    )
    def post(self, request: Request) -> Response:
        return self._create(request)


class MyVideoDetailView(_OwnedRowsView):
    model = HighlightVideo
    serializer_class = HighlightVideoSerializer

    @extend_schema(tags=TAG, summary="Remove a highlight video", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        self._row(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyGuardiansView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Invite a parent or guardian to approve consent",
        request=GuardianInviteSerializer,
        responses={201: PlayerProfileSerializer},
    )
    def post(self, request: Request) -> Response:
        profile = _my_profile(request.user)
        serializer = GuardianInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        if email == request.user.email.lower():
            raise ValidationError({"email": "A guardian must be someone else."})
        if (
            profile.guardians.filter(invited_email__iexact=email)
            .exclude(status=GuardianLink.Status.REVOKED)
            .exists()
        ):
            raise ValidationError({"email": "That guardian is already invited."})
        guardian = User.objects.filter(email__iexact=email).first()
        GuardianLink.objects.create(
            profile=profile,
            invited_email=email,
            guardian=guardian,
            relationship=serializer.validated_data.get("relationship", ""),
        )
        if guardian:
            from apps.notifications.services import notify_users

            notify_users(
                [guardian],
                kind="scouting.guardian_request",
                title="Guardian consent requested",
                body=f"{profile.full_name} asked you to approve their scouting profile.",
                data={"route": "/tabs/scouting/guardian"},
            )
        return Response(_full(profile, request), status=status.HTTP_201_CREATED)


class MyGuardianDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Remove a guardian (their consent stops applying)", responses={204: None}
    )
    def delete(self, request: Request, pk) -> Response:
        link = get_object_or_404(GuardianLink, pk=pk, profile__user=request.user)
        link.status = GuardianLink.Status.REVOKED
        link.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyConsentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="The consent audit trail for my profile",
        responses=ConsentRecordSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        profile = _my_profile(request.user)
        return Response(
            ConsentRecordSerializer(profile.consents.select_related("given_by"), many=True).data
        )


# --- Guardians ---------------------------------------------------------------


class GuardianLinksView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Players who asked me to be their guardian",
        responses=GuardianLinkSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        links = (
            GuardianLink.objects.filter(invited_email__iexact=request.user.email)
            .exclude(status=GuardianLink.Status.REVOKED)
            .select_related("profile", "guardian")
        )
        return Response(GuardianLinkSerializer(links, many=True).data)


def _my_link(request: Request, pk) -> GuardianLink:
    return get_object_or_404(
        GuardianLink.objects.select_related("profile"),
        pk=pk,
        invited_email__iexact=request.user.email,
    )


class GuardianAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Confirm I am this player's guardian",
        request=None,
        responses=GuardianLinkSerializer,
    )
    @transaction.atomic
    def post(self, request: Request, pk) -> Response:
        link = _my_link(request, pk)
        if link.status == GuardianLink.Status.REVOKED:
            raise ValidationError("This request was withdrawn.")
        link.guardian = request.user
        link.status = GuardianLink.Status.ACTIVE
        link.save(update_fields=["guardian", "status", "updated_at"])
        grant_role(request.user, ScoutingRole.Role.GUARDIAN)
        return Response(GuardianLinkSerializer(link).data)


class GuardianDeclineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Decline being this player's guardian",
        request=None,
        responses={204: None},
    )
    def post(self, request: Request, pk) -> Response:
        link = _my_link(request, pk)
        link.status = GuardianLink.Status.REVOKED
        link.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


def _guarded(request: Request, profile_id) -> PlayerProfile:
    profile = get_object_or_404(PlayerProfile, pk=profile_id)
    if not GuardianLink.objects.filter(
        profile=profile, guardian=request.user, status=GuardianLink.Status.ACTIVE
    ).exists():
        raise PermissionDenied("You are not an active guardian for this player.")
    return profile


class GuardianConsentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Grant consent: how visible the profile may be and what it shares",
        request=ConsentDecisionSerializer,
        responses={201: PlayerProfileSerializer},
    )
    def post(self, request: Request, profile_id) -> Response:
        profile = _guarded(request, profile_id)
        serializer = ConsentDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record_consent(
            profile,
            by=request.user,
            given_as="guardian",
            action=ConsentRecord.Action.GRANTED,
            visibility=serializer.validated_data["visibility"],
            sections=serializer.validated_data.get("sections")
            or [item["key"] for item in catalog.CONSENT_SECTIONS if item["required"]],
            note=serializer.validated_data.get("note", ""),
        )
        return Response(_full(profile, request, "guardian"), status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=TAG,
        summary="Revoke consent (the profile becomes private)",
        responses=PlayerProfileSerializer,
    )
    def delete(self, request: Request, profile_id) -> Response:
        profile = _guarded(request, profile_id)
        record_consent(
            profile,
            by=request.user,
            given_as="guardian",
            action=ConsentRecord.Action.REVOKED,
            note=request.query_params.get("note", ""),
        )
        return Response(_full(profile, request, "guardian"))


class GuardianConsentHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Consent audit trail for a player I guard",
        responses=ConsentRecordSerializer(many=True),
    )
    def get(self, request: Request, profile_id) -> Response:
        profile = _guarded(request, profile_id)
        return Response(
            ConsentRecordSerializer(profile.consents.select_related("given_by"), many=True).data
        )


# --- Viewing profiles --------------------------------------------------------


class ProfileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Player profiles I may see",
        responses=dict,
        operation_id="scouting_profiles_list",
    )
    def get(self, request: Request) -> Response:
        sport = request.query_params.get("sport")
        query = (request.query_params.get("q") or "").strip().lower()
        rows = []
        for profile in visible_profiles(request.user):
            if sport and not profile.sports.filter(sport=sport).exists():
                continue
            if (
                query
                and query not in profile.full_name.lower()
                and query not in (profile.school_or_club or "").lower()
            ):
                continue
            rows.append(ProfileCardSerializer(profile).data)
        return Response({"count": len(rows), "results": rows})


class ProfileDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="A player profile, shaped by what I am allowed to see", responses=dict
    )
    def get(self, request: Request, pk) -> Response:
        profile = get_object_or_404(PlayerProfile, pk=pk)
        access = access_level(profile, request.user)
        if access is None:
            # Same answer as a missing profile, so hidden minors cannot be probed.
            raise NotFound("No profile found.")
        if access in {"owner", "guardian"}:
            if request.query_params.get("as") == "scout":
                # Let a player check exactly what a scout would get.
                data = ScoutProfileSerializer(profile, context={"access": "scout"}).data
                data["preview"] = True
                data["effective_visibility"] = effective_visibility(profile)
                return Response(data)
            return Response(_full(profile, request, access))
        return Response(ScoutProfileSerializer(profile, context={"access": access}).data)


class CoachMeasurementView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Coach: record a verified measurement for a player on my team",
        request=MeasurementSerializer,
        responses={201: MeasurementSerializer},
    )
    def post(self, request: Request, pk) -> Response:
        profile = get_object_or_404(PlayerProfile, pk=pk)
        if not coaches_player(request.user, profile):
            raise PermissionDenied("Only a coach of this player's team can verify a measurement.")
        if access_level(profile, request.user) is None:
            raise NotFound("No profile found.")
        serializer = MeasurementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save(
            profile=profile,
            source=Measurement.Source.COACH,
            verified_by=request.user,
            recorded_by=request.user,
        )
        return Response(MeasurementSerializer(row).data, status=status.HTTP_201_CREATED)


# --- Organisations and roles -------------------------------------------------


class OrganisationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Organisations I scout for", responses=OrganisationSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        rows = Organisation.objects.filter(roles__user=request.user).distinct()
        return Response(OrganisationSerializer(rows, many=True, context={"request": request}).data)

    @extend_schema(
        tags=TAG,
        summary="Create an organisation (I become its scout admin)",
        request=OrganisationSerializer,
        responses={201: OrganisationSerializer},
    )
    @transaction.atomic
    def post(self, request: Request) -> Response:
        serializer = OrganisationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        organisation = serializer.save(created_by=request.user)
        grant_role(
            request.user,
            ScoutingRole.Role.SCOUT_ADMIN,
            organisation=organisation,
            granted_by=request.user,
        )
        return Response(
            OrganisationSerializer(organisation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def _organisation_for_admin(request: Request, pk) -> Organisation:
    organisation = get_object_or_404(Organisation, pk=pk)
    if not is_scout_admin_of(request.user, organisation):
        raise PermissionDenied("Only this organisation's scout admins can do that.")
    return organisation


class OrganisationMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Scouts in an organisation", responses=ScoutingRoleSerializer(many=True)
    )
    def get(self, request: Request, pk) -> Response:
        organisation = get_object_or_404(Organisation, pk=pk)
        if not organisation.roles.filter(user=request.user).exists() and not request.user.is_staff:
            raise PermissionDenied("You are not part of this organisation.")
        rows = organisation.roles.select_related("user", "organisation")
        return Response(ScoutingRoleSerializer(rows, many=True).data)

    @extend_schema(
        tags=TAG,
        summary="Scout admin: add a scout or scout admin",
        request=OrganisationMemberWriteSerializer,
        responses={201: ScoutingRoleSerializer},
    )
    def post(self, request: Request, pk) -> Response:
        organisation = _organisation_for_admin(request, pk)
        serializer = OrganisationMemberWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = (
            User.objects.filter(pk=data["user_id"]).first()
            if data.get("user_id")
            else User.objects.filter(email__iexact=data["email"]).first()
        )
        if user is None:
            raise ValidationError("No account with that email. Ask them to sign up first.")
        role = grant_role(user, data["role"], organisation=organisation, granted_by=request.user)
        return Response(ScoutingRoleSerializer(role).data, status=status.HTTP_201_CREATED)


class OrganisationMemberDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Scout admin: remove a scout", responses={204: None})
    def delete(self, request: Request, pk, role_id) -> Response:
        organisation = _organisation_for_admin(request, pk)
        role = get_object_or_404(ScoutingRole, pk=role_id, organisation=organisation)
        admins = organisation.roles.filter(role=ScoutingRole.Role.SCOUT_ADMIN)
        if role.role == ScoutingRole.Role.SCOUT_ADMIN and admins.count() == 1:
            raise ValidationError("An organisation needs at least one scout admin.")
        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachRoleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Become the coach of a team you manage",
        request=CoachRoleSerializer,
        responses={201: ScoutingRoleSerializer},
    )
    def post(self, request: Request) -> Response:
        from apps.competitions.models import Participant

        serializer = CoachRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = get_object_or_404(Participant, pk=serializer.validated_data["team"])
        manages = team.managed_by_id == request.user.id or has_at_least(
            team.competition, request.user, Role.ADMIN
        )
        if not manages:
            raise PermissionDenied(
                "You can coach a team you manage, or one in a competition you run."
            )
        role = grant_role(request.user, ScoutingRole.Role.COACH, team=team, granted_by=request.user)
        return Response(ScoutingRoleSerializer(role).data, status=status.HTTP_201_CREATED)


class MyRoleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Give up one of my scouting roles", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        role = get_object_or_404(ScoutingRole, pk=pk, user=request.user)
        if role.role == ScoutingRole.Role.SCOUT_ADMIN and role.organisation_id:
            admins = ScoutingRole.objects.filter(
                organisation_id=role.organisation_id, role=ScoutingRole.Role.SCOUT_ADMIN
            )
            if admins.count() == 1:
                raise ValidationError("Add another scout admin before you leave.")
        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyTeamsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Teams I could coach (ones I manage or run)", responses=dict)
    def get(self, request: Request) -> Response:
        from django.db.models import Q

        from apps.competitions.models import Membership, Participant

        run = Membership.objects.filter(
            user=request.user, role__in=[Role.OWNER, Role.ADMIN]
        ).values_list("competition_id", flat=True)
        teams = (
            Participant.objects.filter(kind="team")
            .filter(
                Q(managed_by=request.user)
                | Q(competition__owner=request.user)
                | Q(competition_id__in=list(run))
            )
            .select_related("competition")
            .distinct()
        )
        return Response(
            [
                {"id": str(team.id), "name": team.name, "competition": team.competition.name}
                for team in teams
            ]
        )


class PlatformTeamsView(APIView):
    """School and club sides a player can list on their talent profile."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Search teams on Fair Measure to list on a talent profile",
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        from django.db.models import Q

        from apps.competitions.models import Participant
        from apps.competitions.views import visible_competitions

        query = (request.query_params.get("q") or "").strip()
        teams = (
            Participant.objects.filter(
                kind=Participant.Kind.TEAM,
                is_active=True,
                competition__in=visible_competitions(request.user),
            )
            .select_related("competition")
            .order_by("name", "competition__name")
        )
        if query:
            teams = teams.filter(Q(name__icontains=query) | Q(competition__name__icontains=query))
        return Response([team_payload(team) for team in teams[:30]])


# --- Scouting reports ---------------------------------------------------------


class ProfileReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Player scouting report, limited to what I am allowed to see",
        description="Add ?export=1 when printing or saving the report; exports are logged.",
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        from .models import ReportExport
        from .reports import player_report

        profile = get_object_or_404(PlayerProfile.objects.select_related("user"), pk=pk)
        access = access_level(profile, request.user)
        if access is None:
            raise NotFound("No profile found.")
        if request.query_params.get("export") in {"1", "true", "yes"}:
            ReportExport.objects.create(
                viewer=request.user, kind="player_scouting_report", profile=profile, access=access
            )
        return Response(player_report(profile, request.user, access))


# --- League squads -------------------------------------------------------------


NOT_OPEN = (
    "This competition is not open to scouts. Its owner or an admin can turn on "
    "Open to scouts in the competition's setup."
)


def _league(request: Request, pk):
    """A league open to scouts, or a clear reason why it is not available."""

    from apps.competitions.views import visible_competitions

    from .services import scouting_leagues

    league = scouting_leagues(request.user).filter(pk=pk).first()
    if league is not None:
        return league
    if visible_competitions(request.user).filter(pk=pk).exists():
        raise PermissionDenied(NOT_OPEN)
    raise NotFound("No competition found.")


def _is_selector(competition, user) -> bool:
    from .services import is_league_scout

    return has_at_least(competition, user, Role.ADMIN) or is_league_scout(competition, user)


def _assert_selector(competition, user) -> None:
    if not _is_selector(competition, user):
        raise PermissionDenied(
            "Only this competition's owner, admins and league scouts pick the squad."
        )


def _assert_league_admin(competition, user) -> None:
    if not has_at_least(competition, user, Role.ADMIN):
        raise PermissionDenied("Only this competition's owner and admins manage its scouts.")


def _profile_link(profile, viewer) -> tuple[str | None, str]:
    if profile is None or access_level(profile, viewer) is None:
        return None, ""
    return str(profile.id), profile.photo_url


def _pick_row(pick, profiles: dict, viewer) -> dict:
    profile = profiles.get(pick.user_id)
    profile_id, photo = _profile_link(profile, viewer)
    name = (
        (pick.roster_member.name if pick.roster_member_id else "")
        or (profile.full_name if profile else "")
        or pick.user.get_full_name()
    )
    return {
        "id": str(pick.id),
        "user_id": str(pick.user_id),
        "name": name,
        "team": pick.evidence.get("team", ""),
        "position": pick.position_label,
        "group_key": pick.group_key,
        "score": format(pick.score, "f") if pick.score is not None else None,
        "confidence": pick.evidence.get("confidence", "none"),
        "basis": pick.evidence.get("basis", []),
        "summary": pick.evidence.get("summary", []),
        "locked": pick.locked,
        "profile_id": profile_id,
        "photo_url": photo,
    }


def _squad_payload(squad, competition, viewer) -> dict:
    from . import selection

    template = selection.template_for(competition)
    picks = list(squad.picks.select_related("user", "roster_member"))
    profiles = {
        profile.user_id: profile
        for profile in PlayerProfile.objects.filter(user_id__in=[pick.user_id for pick in picks])
    }
    groups = []
    for group in selection.groups_of(template):
        rows = [
            _pick_row(pick, profiles, viewer) for pick in picks if pick.group_key == group["key"]
        ]
        if group["key"] == selection.OTHER_GROUP["key"] and not rows:
            continue
        groups.append(
            {
                "key": group["key"],
                "label": group["label"],
                "min": group.get("min", 0),
                "max": group.get("max"),
                "picks": rows,
            }
        )
    sport_key = selection.league_sport(competition)
    sport = catalog.sport(sport_key or "") or {}
    is_selector = _is_selector(competition, viewer)
    return {
        "id": str(squad.id),
        "competition_id": str(competition.id),
        "competition": competition.name,
        "sport": sport.get("label") or competition.sport,
        "name": squad.name or f"{competition.name} squad",
        "size": squad.size,
        "status": squad.status,
        "notes": squad.notes,
        "filled": len(picks),
        "generated_at": squad.generated_at,
        "published_at": squad.published_at,
        "groups": groups,
        "warnings": selection.squad_warnings(squad, template, picks) if is_selector else [],
        "excluded": [str(item) for item in squad.excluded_users] if is_selector else [],
        "can_edit": is_selector,
    }


def _candidate_row(candidate, viewer, in_squad: set, excluded: set) -> dict:
    profile_id, photo = _profile_link(candidate.profile, viewer)
    return {
        "user_id": str(candidate.user_id),
        "name": candidate.name,
        "team": candidate.team_name,
        "position": candidate.position_label,
        "group_key": candidate.group_key,
        "score": format(candidate.score, "f") if candidate.score is not None else None,
        "available": candidate.available,
        "availability": candidate.availability,
        "in_squad": candidate.user_id in in_squad,
        "excluded": str(candidate.user_id) in excluded,
        "profile_id": profile_id,
        "photo_url": photo,
        **{key: value for key, value in candidate.evidence().items() if key != "components"},
        "components": candidate.evidence()["components"],
    }


class LeagueListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Leagues open to scouts, and the state of each league's squad",
        description=(
            "Also lists sport competitions I run that are not open to scouts yet, "
            "so I can see what turning it on would give."
        ),
        responses=dict,
        operation_id="scouting_leagues_list",
    )
    def get(self, request: Request) -> Response:
        from django.db.models import Count, Q

        from apps.competitions.models import Competition, Membership

        from .models import LeagueScout, LeagueSquad
        from .services import scouting_leagues

        run = Membership.objects.filter(
            user=request.user, role__in=[Role.OWNER, Role.ADMIN]
        ).values_list("competition_id", flat=True)
        mine_closed = Competition.objects.filter(open_to_scouts=False).filter(
            Q(owner=request.user) | Q(pk__in=list(run))
        )
        mine_closed = [
            league for league in mine_closed if catalog.sport_for_competition(league.sport)
        ]
        open_ids = list(scouting_leagues(request.user).values_list("pk", flat=True))
        leagues = (
            Competition.objects.filter(pk__in=[*open_ids, *[c.pk for c in mine_closed]])
            .annotate(
                team_count=Count(
                    "participants",
                    filter=Q(participants__kind="team", participants__is_active=True),
                    distinct=True,
                ),
                scout_count=Count("league_scouts", distinct=True),
            )
            .order_by("-open_to_scouts", "-created_at")[:80]
        )
        squads = {
            squad.competition_id: squad
            for squad in LeagueSquad.objects.filter(competition__in=list(leagues)).annotate(
                filled=Count("picks")
            )
        }
        scouting = set(
            LeagueScout.objects.filter(user=request.user).values_list("competition_id", flat=True)
        )
        rows = []
        for league in leagues:
            squad = squads.get(league.id) if league.open_to_scouts else None
            selector = _is_selector(league, request.user)
            visible_squad = squad if squad and (selector or squad.status == "published") else None
            sport_key = catalog.sport_for_competition(league.sport)
            rows.append(
                {
                    "id": str(league.id),
                    "name": league.name,
                    "sport": (catalog.sport(sport_key or "") or {}).get("label") or league.sport,
                    "sport_key": sport_key,
                    "teams": league.team_count,
                    "open_to_scouts": league.open_to_scouts,
                    "scouts": league.scout_count,
                    "i_scout_it": league.id in scouting,
                    "can_select": selector and league.open_to_scouts,
                    "can_manage": has_at_least(league, request.user, Role.ADMIN),
                    "squad_status": visible_squad.status if visible_squad else None,
                    "squad_filled": visible_squad.filled if visible_squad else 0,
                    "squad_size": (visible_squad.size if visible_squad else None)
                    or catalog.squad_template(sport_key)["size"],
                }
            )
        return Response(rows)


def _scout_rows(competition) -> list[dict]:
    from .models import LeagueScout

    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "name": row.user.get_full_name() or row.user.display_name,
            "organisation": row.organisation.name if row.organisation_id else None,
            "added_at": row.created_at,
        }
        for row in LeagueScout.objects.filter(competition=competition).select_related(
            "user", "organisation"
        )
    ]


class LeagueScoutsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Scouts attached to a league", responses=dict)
    def get(self, request: Request, pk) -> Response:
        competition = _league(request, pk)
        return Response(
            {
                "scouts": _scout_rows(competition),
                "can_manage": has_at_least(competition, request.user, Role.ADMIN),
            }
        )

    @extend_schema(
        tags=TAG,
        summary="Attach a scout to the league (owner and admins)",
        description="The person must already hold a scout or scout admin role.",
        request=dict,
        responses=dict,
    )
    def post(self, request: Request, pk) -> Response:
        from apps.notifications.services import notify_users

        from .models import LeagueScout
        from .services import is_scout, scout_organisations

        competition = _league(request, pk)
        _assert_league_admin(competition, request.user)
        email = str(request.data.get("email") or "").strip()
        person = User.objects.filter(email__iexact=email, is_active=True).first()
        if person is None or not is_scout(person):
            raise ValidationError(
                {"email": "No scout uses that email. They need a scout role in an organisation."}
            )
        organisation = next(iter(scout_organisations(person)), None)
        _, created = LeagueScout.objects.get_or_create(
            competition=competition,
            user=person,
            defaults={"organisation": organisation, "added_by": request.user},
        )
        if not created:
            raise ValidationError({"email": "That scout already follows this league."})
        notify_users(
            [person],
            kind="league.scout_added",
            title=f"You're scouting {competition.name}",
            body="You can now help pick the league's squad.",
            competition=competition,
            category="announcements",
            data={"competition_id": str(competition.id)},
        )
        return Response(
            {"scouts": _scout_rows(competition), "can_manage": True},
            status=status.HTTP_201_CREATED,
        )


class LeagueScoutDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Remove a scout from the league (admins, or the scout themselves)",
        request=None,
        responses=dict,
    )
    def delete(self, request: Request, pk, scout_id) -> Response:
        from .models import LeagueScout

        competition = _league(request, pk)
        row = get_object_or_404(LeagueScout, pk=scout_id, competition=competition)
        if row.user_id != request.user.id:
            _assert_league_admin(competition, request.user)
        row.delete()
        return Response(
            {
                "scouts": _scout_rows(competition),
                "can_manage": has_at_least(competition, request.user, Role.ADMIN),
            }
        )


class LeagueSquadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="The league's squad (drafts only for selectors)",
        description="Add ?export=1 when printing the squad; exports are logged.",
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        from .models import LeagueSquad, ReportExport

        competition = _league(request, pk)
        squad = LeagueSquad.objects.filter(competition=competition).first()
        selector = _is_selector(competition, request.user)
        if squad is None or (squad.status != LeagueSquad.Status.PUBLISHED and not selector):
            return Response({"squad": None, "can_edit": selector, "competition": competition.name})
        if request.query_params.get("export") in {"1", "true", "yes"}:
            ReportExport.objects.create(
                viewer=request.user, kind="league_squad", competition=competition
            )
        return Response({"squad": _squad_payload(squad, competition, request.user)})

    @extend_schema(
        tags=TAG, summary="Rename the squad, change its size or notes", request=dict, responses=dict
    )
    def patch(self, request: Request, pk) -> Response:
        from .models import LeagueSquad

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        squad = get_object_or_404(LeagueSquad, competition=competition)
        if "name" in request.data:
            squad.name = str(request.data["name"])[:120]
        if "notes" in request.data:
            squad.notes = str(request.data["notes"])[:4000]
        if "size" in request.data:
            try:
                size = int(request.data["size"])
            except (TypeError, ValueError) as error:
                raise ValidationError({"size": "Enter a whole number."}) from error
            if not 5 <= size <= 60:
                raise ValidationError({"size": "A squad has between 5 and 60 players."})
            squad.size = size
        squad.save()
        return Response({"squad": _squad_payload(squad, competition, request.user)})


class LeagueSquadGenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Pick (or re-pick) the best squad from the league's data",
        request=None,
        description="Locked picks stay; dropped players stay out.",
        responses=dict,
    )
    def post(self, request: Request, pk) -> Response:
        from . import selection
        from .models import LeagueSquad

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        squad, _ = LeagueSquad.objects.get_or_create(
            competition=competition,
            defaults={
                "size": selection.template_for(competition)["size"],
                "name": f"{competition.name} squad",
            },
        )
        selection.generate(squad, by=request.user)
        return Response({"squad": _squad_payload(squad, competition, request.user)})


class LeagueSquadPublishView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Publish the squad and tell the selected players",
        request=None,
        responses=dict,
    )
    def post(self, request: Request, pk) -> Response:
        from django.utils import timezone

        from apps.notifications.services import notify_users

        from .models import LeagueSquad

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        squad = get_object_or_404(LeagueSquad, competition=competition)
        if not squad.picks.exists():
            raise ValidationError("Pick the squad before publishing it.")
        told = {str(item) for item in squad.notified_users}
        newcomers = [
            pick.user
            for pick in squad.picks.select_related("user")
            if str(pick.user_id) not in told
        ]
        squad.status = LeagueSquad.Status.PUBLISHED
        squad.published_at = timezone.now()
        squad.notified_users = sorted(told | {str(user.id) for user in newcomers})
        squad.save(update_fields=["status", "published_at", "notified_users", "updated_at"])
        if newcomers:
            notify_users(
                newcomers,
                kind="squad.selected",
                title=f"You're in the {squad.name or competition.name + ' squad'}",
                body="The selectors named you in the league squad.",
                competition=competition,
                data={"competition_id": str(competition.id)},
            )
        return Response({"squad": _squad_payload(squad, competition, request.user)})

    @extend_schema(tags=TAG, summary="Take the squad back to draft", request=None, responses=dict)
    def delete(self, request: Request, pk) -> Response:
        from .models import LeagueSquad

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        squad = get_object_or_404(LeagueSquad, competition=competition)
        squad.status = LeagueSquad.Status.DRAFT
        squad.save(update_fields=["status", "updated_at"])
        return Response({"squad": _squad_payload(squad, competition, request.user)})


class LeagueSquadPicksView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Hand-pick a player into the squad", request=dict, responses=dict
    )
    def post(self, request: Request, pk) -> Response:
        from . import selection
        from .models import LeagueSquad

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        squad = get_object_or_404(LeagueSquad, competition=competition)
        pool, _ = selection.candidates(competition)
        wanted = str(request.data.get("user") or "")
        candidate = next((row for row in pool if str(row.user_id) == wanted), None)
        if candidate is None:
            raise ValidationError(
                {"user": "That player is not eligible: they need a visible talent profile."}
            )
        if squad.picks.filter(user_id=candidate.user_id).exists():
            raise ValidationError({"user": "That player is already in the squad."})
        if squad.picks.count() >= squad.size:
            raise ValidationError("The squad is full. Drop a player first.")
        template = selection.template_for(competition)
        group_keys = {group["key"] for group in selection.groups_of(template)}
        group_key = request.data.get("group_key") or candidate.group_key or "other"
        if group_key not in group_keys:
            raise ValidationError({"group_key": "Choose one of the squad's position groups."})
        squad.excluded_users = [
            item for item in squad.excluded_users if str(item) != str(candidate.user_id)
        ]
        squad.save(update_fields=["excluded_users", "updated_at"])
        selection.pick_from(
            candidate, squad, group_key, locked=True, order=squad.picks.count() + 1
        ).save()
        return Response(
            {"squad": _squad_payload(squad, competition, request.user)},
            status=status.HTTP_201_CREATED,
        )


class LeagueSquadPickDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _pick(self, request: Request, pk, pick_id):
        from .models import SquadPick

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        pick = get_object_or_404(SquadPick, pk=pick_id, squad__competition=competition)
        return competition, pick

    @extend_schema(
        tags=TAG,
        summary="Lock a pick in place, or move it to another group",
        request=dict,
        responses=dict,
    )
    def patch(self, request: Request, pk, pick_id) -> Response:
        from . import selection

        competition, pick = self._pick(request, pk, pick_id)
        if "locked" in request.data:
            pick.locked = bool(request.data["locked"])
        if "group_key" in request.data:
            keys = {
                group["key"] for group in selection.groups_of(selection.template_for(competition))
            }
            if request.data["group_key"] not in keys:
                raise ValidationError({"group_key": "Choose one of the squad's position groups."})
            pick.group_key = request.data["group_key"]
            pick.locked = True
        pick.save()
        return Response({"squad": _squad_payload(pick.squad, competition, request.user)})

    @extend_schema(
        tags=TAG,
        summary="Drop a player; re-picking will not bring them back",
        request=None,
        responses=dict,
    )
    def delete(self, request: Request, pk, pick_id) -> Response:
        competition, pick = self._pick(request, pk, pick_id)
        squad = pick.squad
        if str(pick.user_id) not in {str(item) for item in squad.excluded_users}:
            squad.excluded_users = [*squad.excluded_users, str(pick.user_id)]
            squad.save(update_fields=["excluded_users", "updated_at"])
        pick.delete()
        return Response({"squad": _squad_payload(squad, competition, request.user)})


class LeagueSquadRestoreView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Let a dropped player be picked again", request=None, responses=dict
    )
    def delete(self, request: Request, pk, user_id) -> Response:
        from .models import LeagueSquad

        competition = _league(request, pk)
        _assert_selector(competition, request.user)
        squad = get_object_or_404(LeagueSquad, competition=competition)
        squad.excluded_users = [item for item in squad.excluded_users if str(item) != str(user_id)]
        squad.save(update_fields=["excluded_users", "updated_at"])
        return Response({"squad": _squad_payload(squad, competition, request.user)})


class LeagueCandidatesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Every eligible player in the league, ranked (selectors and scouts)",
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        from . import selection
        from .models import LeagueSquad
        from .services import is_scout

        competition = _league(request, pk)
        if not (_is_selector(competition, request.user) or is_scout(request.user)):
            raise PermissionDenied("Only selectors and scouts can see the full ranking.")
        pool, counts = selection.candidates(competition)
        squad = LeagueSquad.objects.filter(competition=competition).first()
        in_squad = set(squad.picks.values_list("user_id", flat=True)) if squad else set()
        excluded = {str(item) for item in squad.excluded_users} if squad else set()
        template = selection.template_for(competition)
        return Response(
            {
                "counts": counts,
                "groups": [
                    {"key": group["key"], "label": group["label"]}
                    for group in selection.groups_of(template)
                ],
                "weights": catalog.SELECTION_WEIGHTS,
                "results": [
                    _candidate_row(candidate, request.user, in_squad, excluded)
                    for candidate in pool
                ],
            }
        )


class MyTeamMembershipsView(APIView):
    """Every team I am on, from accepted invites and rosters, grouped by sport code."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Teams I play for, across competitions, with their sport",
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        from apps.competitions.models import RosterMember, TeamPick

        rows = []
        for entry in (
            RosterMember.objects.filter(user=request.user, participant__is_active=True)
            .select_related("participant__competition")
            .order_by("participant__competition__name", "participant__name")
        ):
            competition = entry.participant.competition
            sport_key = catalog.sport_for_competition(competition.sport)
            rows.append(
                {
                    "id": str(entry.participant_id),
                    "name": entry.participant.name,
                    "competition_id": str(competition.id),
                    "competition": competition.name,
                    "sport": competition.sport,
                    "sport_key": sport_key,
                    "sport_label": (catalog.sport(sport_key or "") or {}).get("label")
                    or (competition.sport or "Other").title(),
                    "position": entry.position,
                    "number": entry.number,
                    "active": entry.is_active,
                    "open_to_scouts": competition.open_to_scouts,
                    "joined_at": entry.created_at,
                }
            )
        pending = TeamPick.objects.filter(user=request.user, status=TeamPick.Status.PENDING).count()
        return Response({"teams": rows, "pending_invites": pending})
