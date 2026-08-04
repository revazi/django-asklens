"""Test-only PostgreSQL override for independent browser verification.

This evidence settings module deliberately ignores live-provider and MCP-row
opt-in environment flags. The reference smoke exports their disabled values as
defense-in-depth in case this module is later refactored to read the environment.
"""

from tests.test_project.demo_settings import *  # noqa: F403
from tests.test_project.demo_settings import build_demo_asklens_settings
from tests.test_project.postgresql_settings import DATABASES as POSTGRESQL_DATABASES

DATABASES = POSTGRESQL_DATABASES
# An empty mapping hard-disables live providers and MCP row return for evidence runs.
DJANGO_ASKLENS = build_demo_asklens_settings({})
