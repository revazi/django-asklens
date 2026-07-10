"""URL routes for the AskLens DRF API."""

from django.urls import path

from django_asklens.api.views import (
    CapabilitiesView,
    CatalogView,
    QueryRunDetailView,
    QueryView,
)

app_name = "django_asklens"

urlpatterns = [
    path("asklens/catalog/", CatalogView.as_view(), name="catalog"),
    path("asklens/capabilities/", CapabilitiesView.as_view(), name="capabilities"),
    path("asklens/query/", QueryView.as_view(), name="query"),
    path("asklens/runs/<int:pk>/", QueryRunDetailView.as_view(), name="run-detail"),
]
