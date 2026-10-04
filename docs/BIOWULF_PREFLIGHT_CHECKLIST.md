# Biowulf preflight checklist

- [ ] Branch, source hash, and reference-commit reconciliation are recorded.
- [ ] Dataset manifests, paths, licenses, and checksums are approved.
- [ ] M0 relevance and query policy are approved for the target dataset.
- [ ] M1/M5 are disabled unless explicit scientific opt-in exists.
- [ ] Model revisions, asset manifests, licenses, and code approvals are recorded.
- [ ] Results, cache, and logs are outside the source checkout.
- [ ] Focused and full tests pass.
- [ ] The plan has explicit rows and no Cartesian expansion.
- [ ] One smoke-array row completed and `jobhist` usage was reviewed.

Classify blockers as `needs_scientific_approval`, `needs_data`,
`needs_model_prefetch`, `needs_biowulf_validation`, or `provenance_unresolved`.
