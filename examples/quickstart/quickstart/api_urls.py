"""Opt-in host login, API, and a framework-free table consumer."""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

from .web_urls import urlpatterns as admin_urls

urlpatterns = [
    *admin_urls,
    path("", include("django_asklens.api.urls")),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="shop/login.html"),
        name="login",
    ),
    path(
        "table/",
        login_required(TemplateView.as_view(template_name="shop/table.html")),
    ),
]
