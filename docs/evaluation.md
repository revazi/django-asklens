# Evaluation fixtures

Evaluation fixtures are deterministic question-to-plan cases used to verify planner, validation, compiler, and renderer behavior without live LLM calls.

The current fixture app is `tests.test_project`, which defines `Customer` and `Order` models. Golden cases live under `tests/evaluation/` and use `DummyProvider` so they require no API keys and make no network calls.

## MVP golden-case themes

- Aggregate orders by status as a bar chart.
- Count orders with a metric visualization.
- Show revenue by month as a line chart.
- List failed orders as a table.
- Average order value by status.

Each case should include:

- natural-language question,
- deterministic QueryPlan payload,
- expected validated plan details,
- expected result rows where database fixtures are involved,
- expected renderer/visualization shape when relevant.

Live-provider evaluations can compare provider output against the same cases, but those tests must remain opt-in and skipped by default.

The current opt-in live evaluation suite covers status aggregation, count metrics, revenue by month, paid-order lists, and an adversarial tenant-field request. Run it with:

```bash
DJANGO_ASKLENS_LIVE_LLM=1 \
DJANGO_ASKLENS_LIVE_LLM_API_KEY="$OPENAI_API_KEY" \
DJANGO_ASKLENS_LIVE_LLM_MODEL="gpt-4.1-mini" \
uv run pytest tests/evaluation/test_live_openai_compatible.py
```

These tests use a small tenant-scoped fixture and still validate provider output before ORM execution. They also assert that unauthorized tenant fields and tenant row values are not returned.
