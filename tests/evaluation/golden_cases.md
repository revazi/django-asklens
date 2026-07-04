# Golden evaluation cases

These cases are mirrored by `tests/evaluation/test_golden_cases.py`.

- Show orders by status as a bar chart.
- How many orders were placed?
- Show revenue by month as a line chart.
- List failed orders.
- Show average order value by status.

They use `DummyProvider` and the `tests.test_project` fixture app. They must remain deterministic and must not require live LLM credentials or network access.
