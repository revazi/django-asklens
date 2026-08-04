"""Test-only PostgreSQL override for independent browser verification."""

from tests.test_project.demo_settings import *  # noqa: F403
from tests.test_project.demo_settings import build_demo_asklens_settings
from tests.test_project.postgresql_settings import DATABASES as POSTGRESQL_DATABASES

DATABASES = POSTGRESQL_DATABASES
DJANGO_ASKLENS = build_demo_asklens_settings({})
