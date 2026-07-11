"""URL routes for the optional AskLens frontend."""

from django.urls import path

from django_asklens.frontend.views import asklens_frontend

app_name = "django_asklens_frontend"

urlpatterns = [
    path("asklens/ui/", asklens_frontend, name="frontend"),
]
