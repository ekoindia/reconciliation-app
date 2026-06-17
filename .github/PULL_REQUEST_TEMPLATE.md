<!--- Provide a general summary of your changes in the Title above -->

## Description
<!--- Describe your changes in detail. -->

## Motivation and Context
<!--- Why is this change required? What problem does it solve? -->
<!--- If it fixes an open issue, please link to the issue here. -->

## Does it change reconciliation behavior?
<!--- Matching rules, ingestion mappings, amount/date parsing, classification, or status
      transitions are load-bearing for financial accuracy — see docs/behavior-contract.md.
      If YES: describe exactly what matches/classifies differently and include before/after
      examples, and confirm finance/ops sign-off. -->
- [ ] No reconciliation behavior change
- [ ] Yes — described above (with before/after examples)

## How Has This Been Tested?
<!--- Describe how you tested your change and the environment you used. -->

## Types of changes
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Checklist
- [ ] Branch is started from and targets the `dev` branch (not `main`).
- [ ] `cd backend && pytest tests/ -q` passes.
- [ ] `cd frontend && npm run build` succeeds.
- [ ] Code follows the project style; `ruff check .` is clean.
- [ ] No real transaction data, account numbers, `.env` values, or database files in the diff.
- [ ] Documentation updated where needed (README / docs / CHANGELOG).
- [ ] I have read the [Contributing Guide](../CONTRIBUTING.md).

## 🙏 Thank you!
Thank you for contributing to Eko Recon. We appreciate your time and effort. 🎉
