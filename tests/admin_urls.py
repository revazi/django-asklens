"""Minimal Django admin URL configuration for admin permission tests."""

from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
