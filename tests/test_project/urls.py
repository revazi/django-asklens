"""URL configuration for the Django AskLens test project."""

from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
