"""Public and platform-admin endpoints for company legal details."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.releases.views import IsPlatformAdmin

from .legal_serializers import CompanyLegalDetailsSerializer
from .models import CompanyLegalDetails


class CompanyLegalPublicView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Legal"], summary="Public company legal details")
    def get(self, request: Request) -> Response:
        solo = CompanyLegalDetails.get_solo()
        return Response(CompanyLegalDetailsSerializer(solo).data)


class CompanyLegalAdminView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(tags=["Platform"], summary="Read company legal details (platform admin)")
    def get(self, request: Request) -> Response:
        solo = CompanyLegalDetails.get_solo()
        return Response(CompanyLegalDetailsSerializer(solo).data)

    @extend_schema(tags=["Platform"], summary="Update company legal details")
    def put(self, request: Request) -> Response:
        return self._save(request)

    @extend_schema(tags=["Platform"], summary="Partially update company legal details")
    def patch(self, request: Request) -> Response:
        return self._save(request, partial=True)

    def _save(self, request: Request, *, partial: bool = False) -> Response:
        solo = CompanyLegalDetails.get_solo()
        serializer = CompanyLegalDetailsSerializer(
            solo, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
