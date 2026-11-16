"""Execute registration guidance and reproduce its structural measurements."""

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from django_asklens.catalog import CatalogRegistry
from tests.test_project.models import Order

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "registration.md"
EXAMPLE = ROOT / "examples" / "quickstart"


def example(name: str) -> str:
    """Read one uniquely marked, trusted Python example from the guide."""

    matches = re.findall(
        rf"<!-- asklens-registration:{name} -->\n```python\n(.*?)\n```",
        GUIDE.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert len(matches) == 1
    return matches[0]


def test_minimal_scoped_registration_uses_existing_public_api(monkeypatch) -> None:
    registry = CatalogRegistry()
    monkeypatch.setattr("django_asklens.catalog.registry.default_registry", registry)

    def visible_orders(_request):
        return Order.objects.none()

    namespace = {"Order": Order, "visible_orders": visible_orders}
    exec(compile(example("minimal"), str(GUIDE), "exec"), namespace)
    resource = namespace["resource"]

    assert registry.get("orders") is resource
    assert resource.label == "Orders"
    assert resource.timezone == "UTC"
    assert resource.scope_mode == "context_scoped"
    assert resource.scope_provider is visible_orders
    assert resource.requires_permission == "orders.view_reports"
    assert set(resource.fields) == {"status"}
    assert resource.fields["status"].label == "Status"
    assert resource.fields["status"].binding == "status"
    assert resource.metrics == {}
    assert registry.to_dict() == {"resources": []}
    assert registry.to_dict(permissions={"orders.view_reports"})["resources"][0][
        "fields"
    ] == [
        {
            "name": "status",
            "label": "Status",
            "type": "string",
            "nullable": False,
            "relation_depth": 0,
        }
    ]


def test_registration_measurements_are_reproducible() -> None:
    for name, expected in (
        ("minimal", (11, 7, 1, 3)),
        ("before", (31, 10, 3, 12)),
        ("after", (21, 10, 3, 10)),
        ("reference", (53, 12, 4, 17)),
    ):
        call = next(
            node
            for node in ast.walk(ast.parse(example(name)))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register"
        )
        fields = next(
            keyword.value for keyword in call.keywords if keyword.arg == "fields"
        )
        assert isinstance(fields, ast.Dict)
        assert (
            call.end_lineno - call.lineno + 1,
            len(call.keywords),
            len(fields.keys),
            sum(len(field.keys) for field in fields.values),
        ) == expected


def test_before_after_and_actual_quickstart_registration_are_equivalent(
    tmp_path,
) -> None:
    """Use the actual consumer model/scope, without duplicating either fixture."""

    project = tmp_path / "consumer"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "db.sqlite3", ".venv"),
    )
    code = (
        "import django\n"
        "django.setup()\n"
        "from django_asklens import register\n"
        "from django_asklens.catalog import default_registry\n"
        "from shop.models import Order\n"
        "from shop.asklens_registration import visible_orders\n"
        "original = default_registry.get('orders')\n"
        f"for code in {[example('before'), example('after')]!r}:\n"
        "    default_registry.clear()\n"
        "    exec(code)\n"
        "    current = default_registry.get('orders')\n"
        "    assert current == original\n"
        "    assert current.to_dict(permissions={'shop.view_order'}) == "
        "original.to_dict(permissions={'shop.view_order'})\n"
        "    assert set(current.fields) == {'product', 'status', 'total_cents'}\n"
        "    assert current.get_scope_queryset(object()).model is Order\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "DJANGO_SETTINGS_MODULE": "quickstart.settings",
        },
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (project / "db.sqlite3").exists()
