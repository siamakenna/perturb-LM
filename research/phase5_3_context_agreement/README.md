# Offline cross-context result diagnostics (#30, #52)

This standalone method inspects existing, hash-bound completed result tables.
It checks literal source-gene identities and complete recorded guide-pair sets
before computing descriptive agreement and contribution diagnostics. It does
not read raw profile vectors, rescore profiles, train models, approve biological
identities, or establish independent biological replication.

The source was preserved after the original diagnostic. A portability change
replaces a machine-specific receipt folder with bounded discovery. Scientific
calculations are unchanged; historical results and their original code hashes
are not rewritten. Expected completed-result hashes remain explicit inputs.

## Synthetic checks

```bash
python3 -m unittest discover -s research/phase5_3_context_agreement -p 'test_*.py' -v
```

## Inspect existing local results

```bash
python3 research/phase5_3_context_agreement/compare_contexts.py --u2os-results /path/to/u2os/results --a549-results /path/to/a549/results
```

Paths must identify the existing ignored result directories containing the
original summaries, manifests, frozen contracts and PRIVATE tables. Explicit
paths work on a different computer after an authorized transfer of those files.
With neither path supplied, bounded local receipt discovery is attempted.
Only a new aggregate diagnostic is written; detailed identities stay local.
Correlations are descriptive, without confidence intervals or p-values.

This source-only PR contains no real result summaries, profiles, private tables,
or investigator-specific absolute paths. It does not rerun the analyses or
change their protocols, PR92, public site, repository settings, or releases.
