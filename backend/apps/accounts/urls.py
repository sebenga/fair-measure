from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    ChangePasswordView,
    GoogleLoginView,
    IdentityDocumentDetailView,
    IdentityDocumentFileView,
    IdentityDocumentListView,
    LoginView,
    MeView,
    ProfileListView,
    RegisterView,
)

app_name = "accounts"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("google", GoogleLoginView.as_view(), name="google-login"),
    path("refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("verify", TokenVerifyView.as_view(), name="token-verify"),
    path("me", MeView.as_view(), name="me"),
    path("me/documents", IdentityDocumentListView.as_view(), name="my-documents"),
    path("me/documents/<uuid:pk>", IdentityDocumentDetailView.as_view(), name="my-document"),
    path(
        "me/documents/<uuid:pk>/file", IdentityDocumentFileView.as_view(), name="my-document-file"
    ),
    path("profiles", ProfileListView.as_view(), name="profiles"),
    path("change-password", ChangePasswordView.as_view(), name="change-password"),
]
