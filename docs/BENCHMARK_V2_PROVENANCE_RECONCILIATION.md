# Benchmark V2 provenance reconciliation

The requested reference commit is now available after a read-only fetch.

| Field | Value |
| --- | --- |
| branch | `feature/benchmark-v2-scikit` |
| current base | `56ec4d08d2b638d0d1d8b8f559ab32e8f0cc15d0` |
| requested commit | `ccec3b94ea6b5061a2d221c553b15e1fb1a93cc1` |
| remote | `origin https://github.com/siamakenna/perturb-LM.git` |
| fetch | `git fetch --all --tags --prune` completed successfully |
| requested commit | available locally; not checked out, merged, or cherry-picked |

The requested commit is not identical to the current base. Its range adds later
Phase 3C comparator work and scientific documentation, including comparator encoder
code, MedCPT/BioLORD revisions, strict comparator tables, M0 provenance/evaluability
documentation, and changes to `phase3c.py` and its tests. No reset, rebase, cherry-pick,
or overwrite was performed.

The frozen fixture still verifies its recorded source/document and local result
checksums. The read-only frozen check reported all eight checksums verified. V2 has
not copied published metric tables or recomputed them; existing result artifacts
remain authoritative.

The unresolved limitation is scientific intent. Later provenance reconstructs
historical M0 as gene-aware, but that does not approve a new production relevance
contract. V2 retains that distinction in its machine-readable contracts.
