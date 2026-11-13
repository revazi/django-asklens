"""Trusted operator CLI: never expose --as-user as an HTTP/MCP identity input."""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.http import HttpRequest

from django_asklens.querying import execute_asklens_query_request


class Command(BaseCommand):
    help = "Ask an exact configured offline question using a synthetic Django user."

    def add_arguments(self, parser):
        parser.add_argument("question")
        parser.add_argument(
            "--as-user", choices=("alice", "bob", "no-report"), default="alice"
        )

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(
                username=f"asklens-{options['as_user']}"
            )
        except get_user_model().DoesNotExist:
            raise CommandError(
                "Run seed_quickstart in this disposable project first."
            ) from None

        # This command is already trusted operator code. In a web application,
        # use the real request.user set by Django authentication middleware.
        request = HttpRequest()
        request.user = user
        outcome = execute_asklens_query_request(
            request,
            question=options["question"],
            include_presentation=False,
        )
        if outcome.response_type == "query":
            document = {"response_type": "query", "result": outcome.payload["result"]}
        elif outcome.response_type == "error":
            document = {"response_type": "error", "error": outcome.payload["error"]}
        else:
            document = {"response_type": "capabilities"}
        self.stdout.write(json.dumps(document, indent=2, sort_keys=True))
        if outcome.response_type != "query":
            raise CommandError("No query result; see the safe response above.")
