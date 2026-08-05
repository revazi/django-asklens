# PR7 deterministic untrusted-plan hardening evidence

This project records a project-controlled, dependency-free, deterministic generation
for untrusted plan boundary rejection coverage.

## Test module

- `tests/execution/test_untrusted_plan_generative.py`

The suite uses stdlib `random.Random` and produces bounded cases in-memory. It
covers malformed syntax, strict-shape failures, unavailable members, budget
limits, operator/type/value mismatches, and unsupported input containers.

## Replay command and seed

```bash
# Fixed default seed
uv run pytest tests/execution/test_untrusted_plan_generative.py

# Optional explicit seed replay
ASKLENS_HARDENING_GENERATION_SEED=20260805 \
  uv run pytest tests/execution/test_untrusted_plan_generative.py
```

This is synthetic generation evidence for boundary safety and is not an
independent security audit or exhaustive fuzzing.
