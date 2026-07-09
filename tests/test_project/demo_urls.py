"""URL configuration for the runnable AskLens test-project demo."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_asklens.api.urls")),
]
