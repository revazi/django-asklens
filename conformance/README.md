# AskLens internal conformance corpus

This directory contains synthetic, implementation-independent JSON cases for
the one current internal contract shape. It is draft and unfrozen. It is not a
published specification or compatibility claim.

Each case contains:

- a permission-scoped catalog snapshot;
- an implementation capability snapshot;
- an untrusted plan;
- an expected canonical result or stable public error;
- the expected application-data query count; and
- a synthetic scenario identifier.

The scenario identifier is not policy input. Each implementation's trusted test
harness owns the identity, permission, row-scope, clock, registration, and
operational-limit setup associated with that identifier. Cases never provide
bindings, query objects, policy tokens, tenant identifiers, or trusted clock
values.

The explicit categories cover positive execution, structural rejection,
member/scope/security behavior, budgets, semantics, ordering/truncation, and
serialization. Generated cases may supplement these documents but must not
replace them.
