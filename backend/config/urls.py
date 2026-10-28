"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.spa import spa_index
from apps.core.views import health_check, version

api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.competitions.urls")),
    path("", include("apps.fixtures.urls")),
    path("", include("apps.standings.urls")),
    path("", include("apps.social.urls")),
    path("", include("apps.media_assets.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.scouting.urls")),
    path("", include("apps.horses.urls")),
    path("", include("apps.results.urls")),
    path("", include("apps.games.urls")),
    path("", include("apps.fantasy.urls")),
    path("", include("apps.marketing.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health_check, name="health"),
    path("api/v1/version", version, name="version"),
    path("api/v1/", include(api_v1)),
    # Called by the BullMQ workers only; protected by INTERNAL_API_TOKEN and
    # excluded from the public schema.
    path("internal/", include("apps.core.urls")),
    # OpenAPI schema + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("", spa_index, name="spa"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "apps.core.spa.not_found"
