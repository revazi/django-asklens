"""No-DRF smoke coverage for the AskLens core package."""

import os
import subprocess
import sys
import textwrap


def test_core_package_works_without_importing_drf() -> None:
    """Core catalog, planning, compiler, execution, and result helpers avoid DRF."""

    code = r"""
import importlib.abc
import sys
from types import SimpleNamespace


class BlockRestFramework(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "rest_framework" or fullname.startswith("rest_framework."):
            raise ModuleNotFoundError("rest_framework is intentionally blocked")
        return None


sys.meta_path.insert(0, BlockRestFramework())

from django.conf import settings

settings.configure(
    SECRET_KEY="test",
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django_asklens",
    ],
    DATABASES={
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    },
    DJANGO_ASKLENS={
        "LLM_BACKEND": "dummy",
        "DUMMY_PLANS": {
            "List users": {
                "resource": "users",
                "intent": "list",
                "select": ["username"],
                "order_by": [{"field": "username", "direction": "asc"}],
                "limit": 10,
                "visualization": {"type": "table"},
            }
        },
    },
    USE_TZ=True,
)

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.management import call_command

from django_asklens import Metric, register, serialize_catalog
from django_asklens.access import can_access_asklens
from django_asklens.catalog.registry import default_registry
from django_asklens.compiler import compile_query_plan
from django_asklens.execution import run_query_plan
from django_asklens.planning import parse_and_validate_query_plan, plan_question
from django_asklens.results import serialize_query_result

call_command("migrate", verbosity=0, interactive=False)
default_registry.clear()
User = get_user_model()
User.objects.create_user(username="alice")
User.objects.create_user(username="bob")

register(
    model=User,
    name="users",
    label="Users",
    fields={"id": {"label": "ID"}, "username": {"label": "Username"}},
    metrics=[Metric("user_count", op="count", field="id")],
)

request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
assert can_access_asklens(request) is True
catalog = serialize_catalog()
assert catalog["resources"][0]["name"] == "users"

planner_result = plan_question("List users")
validated_plan = parse_and_validate_query_plan(
    planner_result.plan.model_dump(mode="json")
)
compiled_query = compile_query_plan(validated_plan)
query_result = run_query_plan(validated_plan)
serialized = serialize_query_result(
    columns=query_result.columns,
    rows=query_result.rows,
    visualization=validated_plan.visualization.model_dump(mode="json"),
)

assert compiled_query.queryset is not None
assert serialized["data"] == [{"username": "alice"}, {"username": "bob"}]
assert "rest_framework" not in sys.modules
"""
    env = dict(os.environ)
    env.pop("DJANGO_SETTINGS_MODULE", None)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
