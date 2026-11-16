"""Optional installed-server Chromium check, driven by a separate dev interpreter."""

import os
import subprocess
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from django_asklens.models import SemanticQueryRun
from shop.recipe_support import assert_metadata_audit, seed


class BrowserRecipeTests(StaticLiveServerTestCase):
    def test_real_host_login_csrf_table_empty_and_opaque_denial(self):
        seed()
        for username in ("asklens-alice", "asklens-no-report"):
            user = get_user_model().objects.get(username=username)
            user.set_password("synthetic-recipe-test-only")
            user.save()
        interpreter = Path(os.environ["ASKLENS_BROWSER_PYTHON"])
        script = Path(os.environ["ASKLENS_BROWSER_SCRIPT"])
        self.assertTrue(interpreter.is_absolute() and interpreter.is_file())
        self.assertTrue(script.is_absolute() and script.is_file())
        outcome = subprocess.run(
            [str(interpreter), str(script), "--base-url", self.live_server_url],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                key: value
                for key, value in os.environ.items()
                if key not in {"PYTHONPATH", "PYTHONHOME", "DJANGO_SETTINGS_MODULE"}
                and not key.startswith("DJANGO_ASKLENS")
            },
        )
        # Never print browser response bodies, credentials, or raw diagnostics.
        self.assertEqual(outcome.returncode, 0, "Installed-server browser check failed")
        self.assertIn("PASS installed-server browser", outcome.stdout)
        self.assertEqual(
            sorted(SemanticQueryRun.objects.values_list("status", flat=True)),
            ["failed", "success", "success"],
        )
        assert_metadata_audit()
