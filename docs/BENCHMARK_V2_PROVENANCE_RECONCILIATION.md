# Benchmark V2 provenance reconciliation

The requested Phase 3C reference commit is available and has been reconciled
against the post-merge Benchmark V2 source tree.

| Field | Value |
| --- | --- |
| post-merge branch | `main` |
| post-merge repair base | `398327163de0d59c764f1ac99e9d2dda283f8380` |
| original Benchmark V2 base | `56ec4d08d2b638d0d1d8b8f559ab32e8f0cc15d0` |
| reconciled Phase 3C reference | `ccec3b94ea6b5061a2d221c553b15e1fb1a93cc1` |
| remote | `origin https://github.com/siamakenna/perturb-LM.git` |
| reconciliation method | read-only Git comparison; no reset, rebase, or cherry-pick |

A read-only comparison confirmed that
`src/perturb_lm/modeling/phase3c.py` and
`scripts/run_phase3c_alignment.py` at the post-merge repair base are
byte-identical to their versions at `ccec3b94`. The earlier frozen fixture had
been constructed from the older `56ec4d0` base and therefore retained stale
pre-`ccec3b94` checksums for those two files.

The frozen fixture is reconciled only for those two source checksums. This is a
provenance and CI repair, not a benchmark rerun. The local result-artifact
checksums, published metric tables, scientific reference path, and existing
scientific results remain unchanged.

Historical M0 remains reconstructed as gene-aware. This reconciliation does not
approve a new production relevance contract, M1, M5, disabled model backends, or
real-data dispatch.

Because the frozen verification compares exact bytes, the repository also pins
LF line endings for the source and documentation files covered by the frozen
contract. This prevents Windows checkout conversion from producing false
checksum failures while leaving the scientific content unchanged.
