from django.urls import path

from .views import EnquiryCreateView, PlacementListView

urlpatterns = [
    path("marketing/placements", PlacementListView.as_view(), name="marketing-placements"),
    path("marketing/enquiries", EnquiryCreateView.as_view(), name="marketing-enquiries"),
]
