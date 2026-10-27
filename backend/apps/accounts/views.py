from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.throttles import AuthRateThrottle

from .serializers import (
    ChangePasswordSerializer,
    FairMeasureTokenObtainPairSerializer,
    GoogleAuthSerializer,
    ProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import get_or_create_user_from_google, verify_google_id_token

User = get_user_model()


def _token_payload(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
    }


@extend_schema(
    tags=["Auth"],
    summary="Sign in with email and password",
    description="Returns an access/refresh token pair plus the signed-in user.",
)
class LoginView(TokenObtainPairView):
    serializer_class = FairMeasureTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]


@extend_schema_view(
    post=extend_schema(
        tags=["Auth"],
        summary="Create an account",
        responses={201: UserSerializer},
    )
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_token_payload(user), status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Auth"],
    summary="Sign in with Google",
    description=(
        "Exchange a Google ID token obtained by the Ionic client for Fair Measure "
        "access and refresh tokens."
    ),
    request=GoogleAuthSerializer,
    responses={200: dict},
)
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claims = verify_google_id_token(serializer.validated_data["id_token"])
        user, created = get_or_create_user_from_google(claims)

        return Response(
            _token_payload(user),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(tags=["Auth"], summary="Get the signed-in user"),
    patch=extend_schema(tags=["Auth"], summary="Update the signed-in user's profile"),
)
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = serializer.save()
        from apps.scouting.services import ensure_player_profile

        ensure_player_profile(user)


@extend_schema(
    tags=["Auth"],
    summary="Change password",
    request=ChangePasswordSerializer,
    responses={204: None},
)
class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Auth"], summary="List profiles that can form a team")
class ProfileListView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    queryset = User.objects.filter(is_active=True).order_by("display_name", "email")


# --- Identity documents (optional, owner-only) ---------------------------------

_SIGNATURES = (
    (b"%PDF", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def _sniff(head: bytes) -> str | None:
    """The real type from the file's first bytes; the browser's label is not trusted."""

    for signature, content_type in _SIGNATURES:
        if head.startswith(signature):
            return content_type
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in {b"heic", b"heix", b"mif1", b"msf1"}:
        return "image/heic"
    return None


def _document_row(document) -> dict:
    return {
        "id": str(document.id),
        "kind": document.kind,
        "kind_label": document.get_kind_display(),
        "original_name": document.original_name,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "uploaded_at": document.uploaded_at,
    }


class IdentityDocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Auth"], summary="My identity documents (optional)", responses=dict)
    def get(self, request: Request) -> Response:
        from .models import IdentityDocument

        rows = IdentityDocument.objects.filter(user=request.user)
        return Response([_document_row(row) for row in rows])

    @extend_schema(
        tags=["Auth"],
        summary="Upload a passport or ID document",
        description=(
            "Multipart form with `kind` (passport or national_id) and `file` (PDF, JPEG, "
            "PNG, WebP or HEIC). Optional. A new upload of the same kind replaces the "
            "old one. Only you can ever download it."
        ),
        request={"multipart/form-data": dict},
        responses={201: dict},
    )
    def post(self, request: Request) -> Response:
        from django.conf import settings

        from .models import IdentityDocument

        kind = request.data.get("kind")
        if kind not in IdentityDocument.Kind.values:
            raise ValidationError({"kind": "Choose passport or ID document."})
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Choose a file to upload."})
        if upload.size > settings.MAX_DOCUMENT_BYTES:
            limit = settings.MAX_DOCUMENT_BYTES // (1024 * 1024)
            raise ValidationError({"file": f"Documents must be {limit} MB or smaller."})
        head = upload.read(16)
        upload.seek(0)
        content_type = _sniff(head)
        if content_type is None:
            raise ValidationError({"file": "Upload a PDF or a photo (JPEG, PNG, WebP or HEIC)."})

        previous = IdentityDocument.objects.filter(user=request.user, kind=kind).first()
        if previous is not None:
            previous.file.delete(save=False)
            previous.delete()
        document = IdentityDocument.objects.create(
            user=request.user,
            kind=kind,
            file=upload,
            original_name=(upload.name or "")[:255],
            content_type=content_type,
            size_bytes=upload.size,
        )
        return Response(_document_row(document), status=status.HTTP_201_CREATED)


class IdentityDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"], summary="Delete one of my identity documents", responses={204: None}
    )
    def delete(self, request: Request, pk) -> Response:
        from .models import IdentityDocument

        document = get_object_or_404(IdentityDocument, pk=pk, user=request.user)
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IdentityDocumentFileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Download one of my identity documents",
        description="Only the owner can download. The response is never cached.",
        responses={(200, "application/octet-stream"): bytes},
    )
    def get(self, request: Request, pk):
        from django.http import FileResponse

        from .models import IdentityDocument

        document = get_object_or_404(IdentityDocument, pk=pk, user=request.user)
        response = FileResponse(
            document.file.open("rb"),
            content_type=document.content_type,
            as_attachment=False,
            filename=document.original_name or f"{document.kind}",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
