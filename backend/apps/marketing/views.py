from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Placement
from .serializers import EnquiryWriteSerializer, PlacementSerializer


class PlacementListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Marketing"], summary="Public commercial placements")
    def get(self, request: Request) -> Response:
        rows = Placement.objects.filter(active=True)
        audience = request.query_params.get("audience")
        slot = request.query_params.get("slot")
        if audience:
            rows = rows.filter(audience=audience)
        if slot:
            rows = rows.filter(slot=slot)
        return Response(PlacementSerializer(rows, many=True).data)


class EnquiryCreateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Marketing"], summary="Send a corporate or government enquiry")
    def post(self, request: Request) -> Response:
        serializer = EnquiryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
