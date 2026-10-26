# Phase 5.3 independent exploratory analysis (#30, #52)

Mac correction v1.0.1 accepts system path aliases above a checkout, including
`/var` versus `/private/var`. It continues to reject output symlinks within
the checkout, escapes, existing destinations and parent-traversal paths.
This changes output-path handling and adds regression tests; scientific
rules and historical results are unchanged. A suitable Python environment
from an earlier attempt can be reused by setting `P5_PYTHON` to its executable.

The user authorized independent cross-guide analysis on 26 October 2026.
This is a new exploratory source-annotation endpoint, separate from the earlier
review-gated protocol and the frozen historical retrieval benchmark. It does
not require coauthor input to execute, and it asserts no coauthor approval.

## Three linked analyses

1. **Cross-guide morphology:** compare cosine agreement between different
   recorded DNA strings with the same source gene label against balanced
   other-source-gene references.
2. **Query information:** count which recorded reagent identities remain
   indistinguishable from category-only versus gene-aware field signatures.
   These are new information summaries, not historical V1/V2 reruns or model scores.
3. **Position and robustness:** evaluate a fixed coordinate-only comparator on
   the same eligible observations and a prespecified spatial-mask sensitivity.

The analyses share one four-plate cohort. They are not independent replications.
The cross-guide effect is conditional on the supplied preprocessed vectors,
source annotations and observed plates. It does not establish reviewed targets,
editing efficacy, independent cultures, biological mechanism or language retrieval.
No model is trained or downloaded. No confidence interval or p-value is produced.

## Inputs and practical scope

The runner retrieves four public `normalized_feature_select_negcon_batch` profiles
for BR00116996–BR00116999 from the immutable CPJUMP1 source revision
`56845c7d4dc322652952783d91dae0ffef47829f`, plus eleven bounded source metadata
files. Git/LFS identities, compressed bytes, matching conditions and row alignment
are verified. The expected capture is 1,536 rows and the unchanged 904 features.
Missing or changed inputs stop the run; no synthetic cohort is substituted.

The compressed profile limit is 16 MiB per file and 64 MiB total. Each metadata
file is limited to 1 MiB and decompressed profiles to 32 MiB each. No images,
bulk production profiles, genome references or private NIH files are retrieved.
This reconstructs four public profiles. It does not verify or replace the
historical private twelve-file manifest on the original Mac.

## One-command Mac handoff

The supplied transfer kit's `run-on-mac.py --publish --execute` creates a fresh
checkout, verifies the pinned design dependencies, copies this study's code,
tests, protocol and CI workflow, and runs invented-data tests. It commits the
source before numerical feature loading. With `--publish`, it pushes a fresh
research branch and verifies its draft PR before execution. PR84 is the base
while open; current main is the base if PR84 has merged. It merges nothing.

It then runs the analyses locally on the Mac. Existing suitable Python is reused
where available. A fresh numerical environment may install pinned NumPy, pandas
and Matplotlib software only. The pipeline uses two concurrent analysis workers
with bounded CPU threads. Biowulf is not used.

## Reproduce from a published checkout

From the clean, committed study checkout with a Python 3.10–3.12 environment
containing NumPy, pandas and Matplotlib:

```bash
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

python -m unittest discover \
  -s research/phase5_3_exploratory -p 'test_*.py' -v

python research/phase5_3_exploratory/run_analysis.py \
  --repo "$PWD" \
  --out "$PWD/outputs/phase53-exploratory-NEW" \
  --fetch-public --authorize-exploratory
```

Use a new output directory each time. An already verified public capture can be
reused with `--staging /absolute/path/to/capture` instead of `--fetch-public`.
Its bytes are verified again before feature loading. Source dependency changes
require fresh review, not removal of the source-pin checks.

## Outputs and interpretation

- `frozen-analysis-contract.json`: source commit, protocol and code hashes saved
  before feature loading.
- `input-capture-binding.json` and `input-receipt.json`: exact public capture
  provenance and input verification.
- `summary.json`: aggregate findings and explicit interpretation limits.
- `report.html`, figures and PDF: local scientific report with all prespecified
  masks, source-group distributions, position control and query-information audit.
- `PRIVATE/`: detailed observation, source-group, coverage and collision ledgers.
- `SHA256SUMS`: all retained output files and their hashes.

All data and results stay in ignored `outputs/`. Publication includes source,
synthetic tests and the protocol, not real-data output tables or results.
`COMPLETE_EXPLORATORY` means the computation and report completed, not that a
biological claim was validated. If no comparison survives the frozen rules,
report the effect as unavailable. Partial or blocked runs retain their evidence.

## Scientific rules

The primary mask requires different plates, different row AND different column.
The secondary mask excludes the same coordinate. Exact reagent, identical DNA
and reverse-complement strings are excluded conservatively. Unknown relations
remain in coverage. Well-like source gene labels, including F10, are held from
cross-guide labels without claiming that the corresponding biological genes
are invalid. No historical query renderer or production F10 guard is changed.

Reference contributions balance physical wells within sequence group, sequence
groups within source gene, and other source genes equally. The existing canonical
weight helper balances complete guide pairs and all plate/guide orientations.
Invalid vectors remain counted and cannot become zero effects. No scaler,
feature selection, batch correction or favorable-group selection occurs.

Read `PROTOCOL.json` for the frozen design and `REPLICATION_PLAN.md` for the next
independent-data step. An additional untouched acquisition/site cohort will add
more scientific value than treating overlapping runs as new experiments.
