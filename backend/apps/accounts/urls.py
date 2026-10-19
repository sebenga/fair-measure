from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    ChangePasswordView,
    GoogleLoginView,
    LoginView,
    MeView,
    ProfileListView,
    RegisterView,
    ThrottledTokenRefreshView,
)

app_name = "accounts"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("google", GoogleLoginView.as_view(), name="google-login"),
    path("refresh", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("verify", TokenVerifyView.as_view(), name="token-verify"),
    path("me", MeView.as_view(), name="me"),
    path("profiles", ProfileListView.as_view(), name="profiles"),
    path("change-password", ChangePasswordView.as_view(), name="change-password"),
]
