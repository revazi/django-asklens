"""URL configuration for the runnable AskLens test-project demo."""

from django.contrib import admin
from django.urls import include, path

from tests.test_project.demo_views import asklens_demo

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", asklens_demo, name="asklens-demo"),
    path("", include("django_asklens.api.urls")),
]
