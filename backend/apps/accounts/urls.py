from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    ChangePasswordView,
    GoogleLoginView,
    LoginView,
    MeView,
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
    path("change-password", ChangePasswordView.as_view(), name="change-password"),
]
