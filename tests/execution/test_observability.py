"""Privacy, failure-isolation, and convergence tests for observability."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from django.db import connection, connections, transaction
from django.test.utils import CaptureQueriesContext

from django_asklens.exceptions import (
    LLMProviderError,
    PublicAskLensError,
    ScopeUnavailableError,
    public_error_payload,
)
from django_asklens.execution import execute_plan
from django_asklens.models import SemanticQueryRun
from django_asklens.observability import (
    ObservabilityEvent,
    _emit_observability_events,
)
from django_asklens.querying import execute_asklens_query_request
from tests.execution.test_facade import (
    build_registry,
    create_order,
    request_with,
    status_plan,
)

pytestmark = pytest.mark.django_db(transaction=True)

PRIVATE_QUESTION = "private-observability-question-140"
PRIVATE_MEMBER = "private.observability.member.140"
PRIVATE_VALUE = "private-observability-value-140"
PRIVATE_DIAGNOSTIC = "private-observability-diagnostic-140"
PRIVATE_IDENTITY = "private-observability-identity-140"
PRIVATE_TENANT = "private-observability-tenant-140"
PRIVATE_PERMISSION = "private.observability.permission.140"
PRIVATE_CREDENTIAL = "private-observability-credential-140"
PRIVATE_DATABASE_ALIAS = "private-observability-database-140"
PRIVATE_SQL = "SELECT private_observability_sql_140"
DOTTED_EVENTS = []
EXPECTED_FIELDS = (
    "name",
    "status",
    "resource",
    "intent",
    "error_code",
    "duration_ms",
    "result_count",
    "truncated",
)


def dotted_sink(event):
    """Capture an event through import-string configuration."""

    DOTTED_EVENTS.append(event)


def configure(settings, sink=None, *, audit_mode="disabled", audit_sink=None):
    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": audit_mode,
        "AUDIT_SINK": audit_sink,
        "OBSERVABILITY_SINK": sink,
    }


def test_event_is_immutable_and_validates_the_exact_allowlist() -> None:
    event = ObservabilityEvent(
        name="asklens.execution.succeeded",
        status="succeeded",
        resource="orders",
        intent="list",
        error_code=None,
        duration_ms=3,
        result_count=1,
        truncated=False,
    )

    assert tuple(field.name for field in fields(event)) == EXPECTED_FIELDS
    with pytest.raises(AttributeError):
        event.resource = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        ObservabilityEvent(**{**asdict(event), "question": PRIVATE_QUESTION})
    with pytest.raises(ValueError):
        ObservabilityEvent(**{**asdict(event), "status": "failed"})
    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="asklens.plan.rejected",
            status="rejected",
            resource=PRIVATE_MEMBER,
            intent="list",
            error_code="asklens.member.unavailable",
            duration_ms=0,
            result_count=None,
            truncated=None,
        )


def test_default_off_preserves_success_and_rejection_query_counts(
    settings,
    django_assert_num_queries,
) -> None:
    configure(settings)
    create_order(email="default-off@example.test", status="paid", total="10.00")

    with django_assert_num_queries(1):
        result = execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )
    assert result.rows == ({"status": "paid"},)

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError),
    ):
        execute_plan(
            {
                "resource": "orders",
                "intent": "list",
                "select": [PRIVATE_MEMBER],
            },
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )


def test_success_events_are_content_free_and_report_bounded_result_metadata(
    settings,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    create_order(email="one@example.test", status=PRIVATE_VALUE, total="10.00")
    create_order(email="two@example.test", status=PRIVATE_VALUE, total="20.00")
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["status"],
        "filters": [{"field": "status", "op": "eq", "value": PRIVATE_VALUE}],
        "limit": 1,
    }

    base_request = request_with(
        "shop.view_orders",
        PRIVATE_PERMISSION,
        visible_status=PRIVATE_VALUE,
    )
    request = SimpleNamespace(
        user=SimpleNamespace(
            get_all_permissions=base_request.user.get_all_permissions,
            is_authenticated=True,
            pk=PRIVATE_IDENTITY,
            username=PRIVATE_IDENTITY,
        ),
        visible_status=base_request.visible_status,
        tenant_id=PRIVATE_TENANT,
        auth=PRIVATE_CREDENTIAL,
        database_alias=PRIVATE_DATABASE_ALIAS,
        raw_sql=PRIVATE_SQL,
    )

    def permissions_getter(current_request):
        assert current_request.user.username == PRIVATE_IDENTITY
        assert current_request.tenant_id == PRIVATE_TENANT
        assert current_request.auth == PRIVATE_CREDENTIAL
        assert current_request.database_alias == PRIVATE_DATABASE_ALIAS
        assert current_request.raw_sql == PRIVATE_SQL
        return base_request.user.permissions

    settings.DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"] = permissions_getter

    with django_assert_num_queries(1):
        result = execute_plan(
            plan,
            request=request,
            registry=build_registry(),
        )

    assert result.row_count == 1 and result.truncated is True
    assert [event.name for event in events] == [
        "asklens.plan.accepted",
        "asklens.execution.succeeded",
    ]
    assert [event.status for event in events] == ["accepted", "succeeded"]
    success = events[-1]
    assert success.resource == "orders"
    assert success.intent == "list"
    assert success.result_count == 1
    assert success.truncated is True
    assert all(event.duration_ms >= 0 for event in events)
    serialized = json.dumps([asdict(event) for event in events])
    for sentinel in (
        PRIVATE_QUESTION,
        PRIVATE_MEMBER,
        PRIVATE_VALUE,
        "one@example.test",
        "two@example.test",
        "customer__email",
        "shop.view_orders",
        PRIVATE_IDENTITY,
        PRIVATE_TENANT,
        PRIVATE_PERMISSION,
        PRIVATE_CREDENTIAL,
        PRIVATE_DATABASE_ALIAS,
        PRIVATE_SQL,
    ):
        assert sentinel not in serialized


def test_unknown_member_rejection_never_reflects_client_names(
    settings,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": [PRIVATE_MEMBER],
        "filters": [{"field": "status", "op": "eq", "value": PRIVATE_VALUE}],
    }

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            plan,
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert public_error_payload(caught.value) == {
        "code": "asklens.member.unavailable",
        "message": "A requested query member is unavailable.",
    }
    assert len(events) == 1
    [event] = events
    assert event == ObservabilityEvent(
        name="asklens.plan.rejected",
        status="rejected",
        resource=None,
        intent=None,
        error_code="asklens.member.unavailable",
        duration_ms=event.duration_ms,
        result_count=None,
        truncated=None,
    )
    serialized = json.dumps(asdict(event))
    assert PRIVATE_MEMBER not in serialized
    assert PRIVATE_VALUE not in serialized


@pytest.mark.parametrize(
    ("failure_stage", "expected_code"),
    [
        ("missing-request", "asklens.authorization.denied"),
        ("permissions", "asklens.authorization.denied"),
        ("audit-context", "asklens.binding.invalid"),
    ],
)
def test_direct_context_rejection_is_opaque_and_does_not_touch_plan_or_audit(
    failure_stage,
    expected_code,
    settings,
    monkeypatch,
    django_assert_num_queries,
) -> None:
    order = []
    events = []

    def audit_sink(_event):
        order.append("audit")

    def observation_sink(event):
        order.append("observability")
        events.append(event)

    configure(
        settings,
        observation_sink,
        audit_mode="custom",
        audit_sink=audit_sink,
    )
    request = request_with("shop.view_orders")
    if failure_stage == "missing-request":
        request = None
    elif failure_stage == "permissions":

        def fail_permissions(_request):
            raise RuntimeError(PRIVATE_DIAGNOSTIC)

        settings.DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"] = fail_permissions
    else:
        settings.DJANGO_ASKLENS["AUDIT_MODE"] = PRIVATE_VALUE

    monkeypatch.setattr(
        "django_asklens.execution.runner._validate_untrusted_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Context rejection parsed the plan.")
        ),
    )

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            {"resource": PRIVATE_MEMBER},
            request=request,
            registry=build_registry(),
        )

    assert caught.value.code == expected_code
    assert caught.value._audit_attempted is False
    assert caught.value._observability_attempted is True
    assert order == ["observability"]
    assert len(events) == 1
    [event] = events
    assert event.name == "asklens.plan.rejected"
    assert event.error_code == expected_code
    assert event.resource is None and event.intent is None
    serialized = json.dumps(asdict(event))
    for sentinel in (PRIVATE_MEMBER, PRIVATE_VALUE, PRIVATE_DIAGNOSTIC):
        assert sentinel not in serialized


def test_shared_context_rejection_defers_observation_until_after_external_audit(
    settings,
    django_assert_num_queries,
) -> None:
    order = []
    events = []
    permission_reads = 0

    def permissions(_request):
        nonlocal permission_reads
        permission_reads += 1
        if permission_reads == 2:
            raise RuntimeError(PRIVATE_DIAGNOSTIC)
        return ()

    def audit_sink(_event):
        order.append("audit")

    def observation_sink(event):
        order.append("observability")
        events.append(event)

    configure(
        settings,
        observation_sink,
        audit_mode="custom",
        audit_sink=audit_sink,
    )
    settings.DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"] = permissions

    with django_assert_num_queries(0):
        outcome = execute_asklens_query_request(
            request_with(),
            question=PRIVATE_QUESTION,
            provided_plan={"resource": PRIVATE_MEMBER},
        )

    assert outcome.response_type == "error"
    assert outcome.payload["error"]["code"] == "asklens.authorization.denied"
    assert permission_reads == 2
    assert order == ["audit", "observability"]
    assert len(events) == 1
    [event] = events
    assert event.name == "asklens.plan.rejected"
    assert event.error_code == "asklens.authorization.denied"
    serialized = json.dumps(asdict(event))
    for sentinel in (PRIVATE_QUESTION, PRIVATE_MEMBER, PRIVATE_DIAGNOSTIC):
        assert sentinel not in serialized


def test_execution_failure_has_safe_resolved_metadata_only(
    settings,
    monkeypatch,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    monkeypatch.setattr(
        "django_asklens.execution.runner._compile_prepared_query",
        lambda _prepared: (_ for _ in ()).throw(RuntimeError(PRIVATE_DIAGNOSTIC)),
    )

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.compile.failed"
    assert [event.name for event in events] == [
        "asklens.plan.accepted",
        "asklens.execution.failed",
    ]
    failed = events[-1]
    assert failed.resource == "orders" and failed.intent == "list"
    assert failed.error_code == "asklens.compile.failed"
    assert failed.result_count is None and failed.truncated is None
    assert PRIVATE_DIAGNOSTIC not in json.dumps([asdict(event) for event in events])


def test_scope_failure_emits_only_safe_execution_metadata(
    settings,
    monkeypatch,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    monkeypatch.setattr(
        "django_asklens.execution.runner._prepare_query_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ScopeUnavailableError(PRIVATE_DIAGNOSTIC)
        ),
    )

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.scope.unavailable"
    assert [event.name for event in events] == [
        "asklens.plan.accepted",
        "asklens.execution.failed",
    ]
    assert events[-1].error_code == "asklens.scope.unavailable"
    assert PRIVATE_DIAGNOSTIC not in json.dumps([asdict(event) for event in events])


def test_budget_rejection_emits_one_opaque_plan_event(
    settings,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    settings.DJANGO_ASKLENS["MAX_SELECTED_FIELDS"] = 0

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.budget.exceeded"
    assert len(events) == 1
    assert events[0].name == "asklens.plan.rejected"
    assert events[0].error_code == "asklens.budget.exceeded"
    assert events[0].resource is None and events[0].intent is None


def test_provider_failure_emits_one_opaque_external_rejection(
    settings,
    monkeypatch,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    settings.DJANGO_ASKLENS["LLM_BACKEND"] = "synthetic"
    monkeypatch.setattr(
        "django_asklens.querying.plan_asklens_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            LLMProviderError(PRIVATE_DIAGNOSTIC)
        ),
    )

    with django_assert_num_queries(0):
        outcome = execute_asklens_query_request(
            request_with(),
            question=PRIVATE_QUESTION,
        )

    assert outcome.response_type == "error"
    assert outcome.payload["error"]["code"] == "asklens.provider.failed"
    assert len(events) == 1
    assert events[0].name == "asklens.plan.rejected"
    assert events[0].error_code == "asklens.provider.failed"
    assert events[0].resource is None and events[0].intent is None
    serialized = json.dumps(asdict(events[0]))
    assert PRIVATE_QUESTION not in serialized
    assert PRIVATE_DIAGNOSTIC not in serialized


def test_custom_audit_sink_failure_does_not_hide_observability_or_change_result(
    settings,
    django_assert_num_queries,
) -> None:
    events = []

    def failing_audit_sink(_event):
        raise RuntimeError(PRIVATE_DIAGNOSTIC)

    configure(
        settings,
        events.append,
        audit_mode="custom",
        audit_sink=failing_audit_sink,
    )
    create_order(email="audit-failure@example.test", status="paid", total="10.00")

    with django_assert_num_queries(1):
        result = execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert result.to_dict()["data"] == [{"status": "paid"}]
    assert [event.name for event in events] == [
        "asklens.plan.accepted",
        "asklens.execution.succeeded",
    ]
    assert PRIVATE_DIAGNOSTIC not in json.dumps([asdict(event) for event in events])


def test_observability_runs_after_audit_and_sink_failures_do_not_change_success(
    settings,
    django_assert_num_queries,
) -> None:
    order = []

    def audit_sink(_event):
        order.append("audit")

    def failing_observability_sink(event):
        order.append(event.name)
        raise RuntimeError(PRIVATE_DIAGNOSTIC)

    configure(
        settings,
        failing_observability_sink,
        audit_mode="custom",
        audit_sink=audit_sink,
    )
    create_order(email="sink-failure@example.test", status="paid", total="10.00")

    with django_assert_num_queries(1):
        result = execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert result.to_dict()["data"] == [{"status": "paid"}]
    assert order == ["audit", "asklens.plan.accepted"]


def test_sink_database_failure_is_deferred_and_cannot_rollback_audit(
    settings,
) -> None:
    sink_calls = []

    def failing_database_sink(event):
        sink_calls.append(event.name)
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM private_observability_missing_table_140")

    configure(settings, failing_database_sink, audit_mode="database")
    create_order(email="transaction@example.test", status="paid", total="10.00")

    with transaction.atomic():
        result = execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )
        assert sink_calls == []
        assert SemanticQueryRun.objects.filter(pk=result._audit_record.pk).exists()

    assert result.to_dict()["data"] == [{"status": "paid"}]
    assert sink_calls == ["asklens.plan.accepted"]
    assert SemanticQueryRun.objects.filter(pk=result._audit_record.pk).exists()
    assert connection.needs_rollback is False


def test_rolled_back_caller_transaction_drops_deferred_events(settings) -> None:
    events = []
    configure(settings, events.append, audit_mode="database")

    with pytest.raises(RuntimeError, match="synthetic rollback"):
        with transaction.atomic():
            execute_plan(
                status_plan(),
                request=request_with("shop.view_orders"),
                registry=build_registry(),
            )
            assert events == []
            raise RuntimeError("synthetic rollback")

    assert events == []
    assert not SemanticQueryRun.objects.exists()


def test_manual_transaction_management_drops_observations_and_preserves_audit(
    settings,
) -> None:
    sink_calls = []

    def failing_database_sink(event):
        sink_calls.append(event.name)
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM private_observability_missing_table_140")

    configure(settings, failing_database_sink, audit_mode="database")
    create_order(email="manual-transaction@example.test", status="paid", total="10.00")

    transaction.set_autocommit(False)
    try:
        result = execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )
        assert sink_calls == []
        transaction.commit()
    finally:
        if connection.needs_rollback:
            transaction.rollback()
        transaction.set_autocommit(True)

    assert sink_calls == []
    assert result.to_dict()["data"] == [{"status": "paid"}]
    assert SemanticQueryRun.objects.filter(pk=result._audit_record.pk).exists()


@pytest.mark.django_db(
    transaction=True,
    databases=["default", "asklens_read"],
)
def test_multi_database_rollback_drops_batch_even_when_other_database_commits() -> None:
    events = []
    event = ObservabilityEvent(
        name="asklens.plan.rejected",
        status="rejected",
        resource=None,
        intent=None,
        error_code="asklens.plan.invalid",
        duration_ms=0,
        result_count=None,
        truncated=None,
    )

    # Ensure both wrappers are initialized before the emission-time snapshot.
    connections["default"].ensure_connection()
    connections["asklens_read"].ensure_connection()
    with transaction.atomic(using="default"):
        with pytest.raises(RuntimeError, match="secondary rollback"):
            with transaction.atomic(using="asklens_read"):
                _emit_observability_events(sink=events.append, events=(event,))
                assert events == []
                raise RuntimeError("secondary rollback")
        assert events == []

    assert events == []


def test_invalid_or_unresolvable_sink_is_disabled_safely(
    settings,
    django_assert_num_queries,
) -> None:
    for sink in (object(), "private_observability_backend_140.missing"):
        configure(settings, sink)
        with django_assert_num_queries(1):
            result = execute_plan(
                status_plan(),
                request=request_with("shop.view_orders"),
                registry=build_registry(),
            )
        assert result.row_count == 0


def test_dotted_sink_resolves_and_receives_typed_events(settings) -> None:
    DOTTED_EVENTS.clear()
    configure(settings, f"{__name__}.dotted_sink")

    result = execute_plan(
        status_plan(),
        request=request_with("shop.view_orders"),
        registry=build_registry(),
    )

    assert result.row_count == 0
    assert [event.name for event in DOTTED_EVENTS] == [
        "asklens.plan.accepted",
        "asklens.execution.succeeded",
    ]
    assert all(isinstance(event, ObservabilityEvent) for event in DOTTED_EVENTS)


@pytest.mark.parametrize("audit_mode", ["disabled", "custom", "database"])
def test_failing_sink_preserves_rejection_audit_and_zero_application_sql(
    audit_mode,
    settings,
    monkeypatch,
) -> None:
    order = []

    def audit_sink(_event):
        order.append("audit")

    def observability_sink(event):
        order.append(event.name)
        raise RuntimeError(PRIVATE_DIAGNOSTIC)

    configure(
        settings,
        observability_sink,
        audit_mode=audit_mode,
        audit_sink=audit_sink,
    )
    compiler = lambda _prepared: (_ for _ in ()).throw(  # noqa: E731
        AssertionError("Rejected plan reached compilation.")
    )
    monkeypatch.setattr(
        "django_asklens.execution.runner._compile_prepared_query", compiler
    )

    with CaptureQueriesContext(connection) as captured:
        with pytest.raises(PublicAskLensError) as caught:
            execute_plan(
                {
                    "resource": "orders",
                    "intent": "list",
                    "select": [PRIVATE_MEMBER],
                },
                request=request_with("shop.view_orders"),
                registry=build_registry(),
            )

    assert caught.value.code == "asklens.member.unavailable"
    sql = [query["sql"].upper() for query in captured]
    assert len(sql) == (1 if audit_mode == "database" else 0)
    assert all("TEST_PROJECT_ORDER" not in statement for statement in sql)
    expected_prefix = ["audit"] if audit_mode == "custom" else []
    assert order == [*expected_prefix, "asklens.plan.rejected"]


def test_reentrant_emission_is_suppressed() -> None:
    calls = []
    event = ObservabilityEvent(
        name="asklens.plan.rejected",
        status="rejected",
        resource=None,
        intent=None,
        error_code="asklens.plan.invalid",
        duration_ms=0,
        result_count=None,
        truncated=None,
    )

    def sink(received):
        calls.append(received)
        _emit_observability_events(sink=sink, events=(received,))

    _emit_observability_events(sink=sink, events=(event,))
    assert calls == [event]


def test_concurrent_emission_is_context_local() -> None:
    event = ObservabilityEvent(
        name="asklens.plan.rejected",
        status="rejected",
        resource=None,
        intent=None,
        error_code="asklens.plan.invalid",
        duration_ms=0,
        result_count=None,
        truncated=None,
    )
    barrier = Barrier(2)
    lock = Lock()
    calls = []

    def sink(received):
        barrier.wait(timeout=2)
        with lock:
            calls.append(received)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _emit_observability_events,
                sink=sink,
                events=(event,),
            )
            for _ in range(2)
        ]
        for future in futures:
            future.result(timeout=3)

    assert calls == [event, event]


def test_capability_help_does_not_claim_a_plan_or_execution_event(
    settings,
    django_assert_num_queries,
) -> None:
    events = []
    configure(settings, events.append)
    settings.DJANGO_ASKLENS["LLM_BACKEND"] = "dummy"

    with django_assert_num_queries(0):
        outcome = execute_asklens_query_request(
            request_with(),
            question="What can I ask?",
        )

    assert outcome.response_type == "capabilities"
    assert events == []


def test_shared_orchestration_emits_no_duplicate_facade_events(
    settings,
    django_assert_num_queries,
) -> None:
    from django_asklens.catalog.registry import default_registry

    events = []
    configure(settings, events.append)
    default_registry.clear()
    resource = build_registry().get("orders")
    default_registry.register(
        model=resource.model,
        name=resource.name,
        timezone=resource.timezone,
        fields=resource.fields,
        metrics=tuple(resource.metrics.values()),
        requires_permission=resource.requires_permission,
        scope_mode=resource.scope_mode,
        scope_provider=resource.scope_provider,
    )
    try:
        with django_assert_num_queries(1):
            outcome = execute_asklens_query_request(
                request_with("shop.view_orders"),
                question=PRIVATE_QUESTION,
                provided_plan=status_plan().model_dump(mode="json"),
            )
    finally:
        default_registry.clear()

    assert outcome.response_type == "query"
    assert [event.name for event in events] == [
        "asklens.plan.accepted",
        "asklens.execution.succeeded",
    ]
    assert PRIVATE_QUESTION not in json.dumps([asdict(event) for event in events])


def test_api_admin_and_mcp_converge_on_the_same_two_events(
    settings,
    django_assert_num_queries,
) -> None:
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from django_asklens.admin_querying import execute_admin_query
    from django_asklens.catalog.registry import default_registry
    from django_asklens.mcp import asklens_query

    events = []
    question = "Synthetic adapter convergence"
    plan = status_plan().model_dump(mode="json")
    configure(settings, events.append)
    settings.DJANGO_ASKLENS.update(
        {
            "LLM_BACKEND": "dummy",
            "DUMMY_PLANS": {question: {"query_plan": plan}},
            "REQUEST_PERMISSIONS_GETTER": lambda _request: (),
        }
    )
    resource = build_registry().get("orders")
    default_registry.clear()
    default_registry.register(
        model=resource.model,
        name=resource.name,
        timezone=resource.timezone,
        fields=resource.fields,
        metrics=tuple(resource.metrics.values()),
        scope_mode="global",
    )
    user = get_user_model().objects.create_user(username="observability-adapter")
    request = SimpleNamespace(user=user)
    client = APIClient()
    client.force_authenticate(user=user)

    try:
        calls = (
            lambda: client.post(
                "/asklens/query/", {"question": question}, format="json"
            ),
            lambda: execute_admin_query(request, question=question),
            lambda: asklens_query(request, question),
        )
        for call in calls:
            events.clear()
            with django_assert_num_queries(1):
                call()
            assert [event.name for event in events] == [
                "asklens.plan.accepted",
                "asklens.execution.succeeded",
            ]
    finally:
        default_registry.clear()


def test_pre_facade_rejection_is_emitted_once_after_external_audit(settings) -> None:
    order = []
    events = []

    def audit_sink(_event):
        order.append("audit")

    def observation_sink(event):
        order.append("observability")
        events.append(event)

    configure(
        settings,
        observation_sink,
        audit_mode="custom",
        audit_sink=audit_sink,
    )
    outcome = execute_asklens_query_request(
        SimpleNamespace(user=SimpleNamespace(get_all_permissions=lambda: set())),
        question=PRIVATE_QUESTION,
        provided_plan={},
        provided_presentation={"kind": PRIVATE_VALUE},
    )

    assert outcome.response_type == "error"
    assert order == ["audit", "observability"]
    assert len(events) == 1
    [event] = events
    assert event.name == "asklens.plan.rejected"
    assert event.error_code == "asklens.parse.invalid"
    assert event.resource is None and event.intent is None
    serialized = json.dumps(asdict(event))
    assert PRIVATE_QUESTION not in serialized
    assert PRIVATE_VALUE not in serialized
