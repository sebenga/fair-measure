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
        "sports", "measurements", "injuries", "videos", "guardians"
    ).get(pk=profile.pk)
    return PlayerProfileSerializer(profile, context={"request": request, "access": access}).data


# --- Catalogue and "me" ------------------------------------------------------


class CatalogView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG, summary="Sports, positions, age groups and consent sections", responses=dict
    )
    def get(self, request: Request) -> Response:
        return Response(catalog.public_catalog())


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
            if query and query not in profile.full_name.lower():
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
