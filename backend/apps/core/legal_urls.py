from django.urls import path

from . import legal_views

urlpatterns = [
    path(
        "legal/company",
        legal_views.CompanyLegalPublicView.as_view(),
        name="legal-company",
    ),
    path(
        "platform/admin/legal",
        legal_views.CompanyLegalAdminView.as_view(),
        name="platform-admin-legal",
    ),
]
