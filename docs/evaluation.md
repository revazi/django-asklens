# Evaluation fixtures

Evaluation fixtures are deterministic question-to-plan cases used to verify planner, validation, compiler, result serialization, and visualization-hint behavior without live LLM calls.

The current fixture app is `tests.test_project`, which defines `Customer` and `Order` models. Golden cases live under `tests/evaluation/` and use `DummyProvider` so they require no API keys and make no network calls.

## Golden-case themes

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
- expected serialized result and visualization-hint shape when relevant.

Live-provider evaluations can compare provider output against the same cases, but those tests must remain opt-in and skipped by default.

The current opt-in live evaluation suite covers status aggregation, count metrics, revenue by month, paid-order lists, an adversarial tenant-field request, and the full DRF `/asklens/query/` path.

Default CI and local test runs do not set live-provider environment variables, so these tests are skipped by default.

Required environment variables for live evaluation:

- `DJANGO_ASKLENS_LIVE_LLM=1`
- `DJANGO_ASKLENS_LIVE_LLM_API_KEY` with the provider API key
- `DJANGO_ASKLENS_LIVE_LLM_MODEL` with the provider model name

Optional environment variable:

- `DJANGO_ASKLENS_LIVE_LLM_BASE_URL` for a non-default OpenAI-compatible base URL

Run the live evaluation suite with:

```bash
DJANGO_ASKLENS_LIVE_LLM=1 \
DJANGO_ASKLENS_LIVE_LLM_API_KEY="$OPENAI_API_KEY" \
DJANGO_ASKLENS_LIVE_LLM_MODEL="gpt-4.1-mini" \
uv run pytest tests/evaluation/test_live_openai_compatible.py \
  tests/evaluation/test_live_api_openai_compatible.py
```

For Gemini through the OpenAI-compatible endpoint, set `DJANGO_ASKLENS_LIVE_LLM_API_KEY` from `GEMINI_API_KEY`, choose a Gemini model, and set `DJANGO_ASKLENS_LIVE_LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"`.

These tests use small tenant-scoped fixtures and still validate provider output before ORM execution. They also assert that unauthorized tenant fields and tenant row values are not returned. The API evaluation additionally verifies query-run auditing through the DRF endpoint.
