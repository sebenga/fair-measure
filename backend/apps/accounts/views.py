from __future__ import annotations

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

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
