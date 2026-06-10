## What does this PR do?

<!-- One or two sentences. -->

## Does it change reconciliation behavior?

<!-- Matching rules, ingestion mappings, amount/date parsing, status transitions.
     If YES: describe exactly what matches differently and include before/after examples. -->

- [ ] No reconciliation behavior change
- [ ] Yes — described above

## Checklist

- [ ] `cd backend && pytest tests/ -q` passes
- [ ] `cd frontend && npm run build` succeeds
- [ ] No real transaction data, `.env` values, or database files in the diff
