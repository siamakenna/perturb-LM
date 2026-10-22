# Local metadata feasibility: exact reagent and different-sequence support

2026-10-20. Related issues: #30 and #52. Descriptive metadata audit only;
no scientific approval, predictive queries, numeric feature parsing, scaler,
retrieval scores, fitted model or inference. PR77/83 remain unmerged proposals;
this implementation starts from merged main `c0518710d38adb17a21e150db45b0388a503b030`.

## Inputs and preservation

Use the complete original Phase 5 `local_mapping_PRIVATE.csv`,
`profile_manifest.json`, `cohort_summary.json`, `source/provenance.json`,
the eleven original source files and the twelve existing compressed profiles.
The auditor verifies all profile/source hashes and file sets, reads only profile
headers and metadata, and reproduces the complete original mapping in memory.
It never reconstructs missing records from historical counts or overwrites an
original artifact. The mapping itself has no prior frozen own-file digest;
its current hash binds this run, while raw-row/source-join agreement checks
its completeness independently. Disagreements stop the census and are reported.

The fixed matched stratum is the existing four U2OS/Cas9 CRISPR plates
BR00116996–BR00116999. The merged Phase 5.1 validator, well canonicalization and
plate-role enumeration are shared with the planner. Its thresholded planning
entry point is not called. No minimum study size is chosen; synthetic 3/2
settings remain test parameters only. Contradictory selected identities,
conditions, source/local gene or sequence annotations, and duplicate physical
wells stop the census even when old flags say `resolved=true`.

## Support definitions

A is exact-reagent gallery support. B is **provisional source-gene-string /
different-sequence capacity**: a different reagent ID, a different valid DNA
sequence and the same unambiguous source gene string. Equal sequence strings
under different IDs never establish B. Missing/ambiguous sequence or gene
annotations are counted, never guessed. Sequence validation means only a
nonempty A/C/G/T string after trimming and uppercasing; no unapproved length,
targeting, efficacy or stable-identity rule is invented. Source gene strings are
not stable reviewed genes. A sequence associated with multiple source gene
strings is excluded from B. No biological positive labels are approved.

Both endpoints use the full labeled noncontrol gallery, identical recorded
conditions, different query/gallery physical plates, and each spatial mask:
(a) different canonical well coordinate; (b) different row AND different column.
Queries without support remain in coverage denominators. Raw gallery support
is separate from support where the query reagent occurs on the other two
training plates. A further count requires a surviving positive reagent to occur
in training as well. This does not establish unseen-guide or unseen-gene transfer.

Counts distinguish physical wells, reagent IDs, valid sequence strings, source
gene strings, reviewed stable genes (none supplied) and plates. Positive pair
counts are separate from unique gallery wells. Twelve role assignments reuse
four plates and do not constitute twelve independent experiments.

## Preprocessing and execution

The preserved source README documents CellProfiler aggregation, Pycytominer,
MAD normalization variants and invariant/redundant feature filtering. The exact
fit populations and parameters for the selected `negcon_batch` artifact bytes
remain unknown. Matching 904-feature schemas cannot establish training-only
preprocessing. New scaling would not undo prior held-out information. Culture
independence, guide efficacy and independent stable gene/guide review remain
unresolved. WGA and all recorded culture/acquisition distinctions are retained.
The F10 production identifier guard remains unchanged; this auditor renders no
queries and provides no guard exception.

Run synthetic tests first:

```bash
PYTHONPATH=src python -m pytest -q tests/test_phase5_guide_support.py \
  tests/test_phase5_1_rotations.py tests/test_phase5_audits.py
```

Then, with local variables pointing to the preserved inputs and inspected
aggregate validation/context records:

```bash
P5_CODE_ROOT="$PWD"
(
cd "$P5_INPUT_ANCHOR"
PYTHONPATH="$P5_CODE_ROOT/src" "$P5_PYTHON" \
  "$P5_CODE_ROOT/scripts/audit_phase5_guide_support.py" \
  --audit-root "$P5_AUDIT_ROOT" --data-root "$P5_PROFILE_ROOT" \
  --evidence-root "$P5_EVIDENCE_ROOT" \
  --validation "$P5_VALIDATION" --repository-context "$P5_CONTEXT" \
  --out "$P5_CODE_ROOT/outputs/guide-support-FRESH-RUN"
)
```

Start in the repository. Set `P5_PYTHON` to the absolute validated interpreter
path and `P5_INPUT_ANCHOR` to the trusted invocation directory containing the
aggregate evidence. `P5_EVIDENCE_ROOT` contains both validation and context
JSONs; it defaults to the invocation directory and can only narrow beneath it.
It cannot grant access outside that directory. These JSON inputs must be
regular files beneath the root, without descendant symlinks or parent
traversal, and at most 4 MiB. Parsing and SHA-256 use the same byte snapshot;
aliases above the invocation directory remain valid on macOS.

The directory must be fresh and Git-ignored. The only census outputs are the
aggregate `metadata-support-summary.json` and its `SHA256SUMS`, with private
permissions. Input locations, rows, guide sequences and mappings stay local;
the summary uses logical input labels and aggregate counts. It records the
actual Git SHA, implementation hashes, source revision, input manifest hashes,
executed validation and remaining decisions. No draft branch code is executed.
