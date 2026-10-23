# Phase 5.2: completed Batch8 pilot and next scientific decision

Record prepared 2026-10-15. Related issues: #30, #52. Continues Phase 5.1 / PR #76.

**Completed:** a bounded public-data morphology-recovery pilot executed on the
operator's Mac on 2026-10-14. **Pending:** collaborator adjudication, manuscript
scope, independent biological relevance and approval of a subsequent experiment.
No pretrained inference was performed. Frozen historical benchmarks are unchanged.

## Scope and observed results

The gallery was Target1 plate BR00123523; queries were Target2 plate BR00121428,
both source_4 / 2021_07_12_Batch8. Relevance required equal complete design Broad
sample IDs and agreement of production JCP IDs. These are design-assigned labels,
not independently verified stock delivery or biological target engagement.

There were 147 gallery entries and 147 query entries, all 147 evaluable, with no
retained query lacking a positive. Equal weight was given to each eligible exact
sample label. The unit is a query label conditional on this single plate pair.
There are no independent-plate confidence intervals, p-values or power claims.

| Method | Mean reciprocal rank | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Morphology | 0.1639553 | 0.1020408 | 0.1972789 | 0.2448980 |
| Uniform-rank expectation | 0.0379707 | 0.0068186 | 0.0340928 | 0.0681857 |
| Coordinate-only control | 0.0391574 | 0.0034014 | 0.0408163 | 0.0841270 |

Morphology had higher average recovery metrics than both references within this
selected pair. This supports a limited feasibility observation. It does not
establish biological-relation retrieval, language performance, independent
replication or generalization. The coordinate control tests one spatial ranking
rule, not all positional artifacts. No additional unmatched gallery identities
survived selection, so this is a restricted matched-cohort experiment.

Each design began with 384 positions: removing 60 design positive controls and
64 DMSO positions left 260 included treatment positions; excluding six additional
production positive controls left 254; the subsequent identity/duplicate rules
left 147. This ordered accounting is not a sum of overlapping reason flags.
The retained cohort is 56.5% of 260 treatment positions and 94.8% of 155 originally
shared exact design IDs. Many-to-one sample/JCP relationships are not themselves
proof of erroneous metadata. The conservative one-to-one rule excludes them.
Target2's absent H14 was a design control; excluded design positions must not be
reported as an equal number of removed observed profile rows on both plates.

## Frozen pilot method

The pilot used 3,673 prespecified Cells_, Cytoplasm_ and Nuclei_ features. Image_
features were excluded by scope, not assumed devoid of biological information.
Only 64 Target1 DMSO wells fitted per-feature medians and 1.4826 times MAD.
The positive-finite-MAD rule removed 78 features, leaving 3,595. The frozen
transformation was applied to both plates; Target2 did not fit preprocessing.
Upstream source preprocessing/fit populations remain unverified.

Scoring used float64 cosine similarity, a canonical same-coordinate exclusion
and analytic averaging over exact-score ties. Uniform-rank references used the
same per-query candidate counts. Controls from either annotation source and
ambiguous/duplicate identity mappings were excluded with local ledgers.
Chemical-key matches were not used to collapse distinct samples. Nonfinite or
zero-norm eligible transformed profiles fail before metric publication.

Dose, exposure, culture independence and upstream processing remain unresolved.
One shared batch and one plate per layout cannot isolate a causal layout effect.
Additional Target1 plates sharing this Target2 plate would not create independent
cross-layout replication. DINOv2 and additional compute are lower priorities.

## Evidence and provenance

The original aggregate evidence remains under ignored local outputs in accordance
with AGENTS.md and EVALUATION_PROTOCOL.md. This authored record preserves reviewed
findings and evidence hashes. Row-level ledgers, profiles, fitted parameters,
environments and generated reports are not committed.

- `pilot-summary.json` SHA256: `2fa25b216e6f2f3c0e93a90a4d5c67649da27a79f73e3e8c8e2e337efaa5ceea`.
- `approved-plan.json` SHA256: `4ab036385405a0d7982b4f22692fe0bdacaf0811163d582ebe7919ec646680ce`.
- Execution timestamp in the summary: `2026-10-14T18:43:30.690398+00:00`.
- Runtime recorded by the execution: macOS 15.8.1 arm64; Python 3.12.15;
  NumPy 2.3.5; PyArrow 24.0.0; Matplotlib 3.10.8.
- Project baseline: `c0518710d38adb17a21e150db45b0388a503b030`.
- Public design metadata: [JUMP-Target](https://github.com/jump-cellpainting/JUMP-Target/tree/2da0551610a26548a384537b28d05f6fc72ea33c).
- Production metadata: [JUMP datasets](https://github.com/jump-cellpainting/datasets/tree/016e865fa0691244e0860943e41c7d6a88ed2580).

The plan hash matches the summary. The plan's preparation-time
`PROPOSED_NOT_APPROVED` / `execution_performed:false` fields are immutable history;
operator approval and completion are recorded in the separate summary. Do not
edit the plan to make its status look current. Operator execution approval is
not collaborator approval of biological claims or a new benchmark contract.

### Input byte bindings from the executed plan

| Role | SHA256 |
|---|---|
| annotation_ledger | `0398a6a76910b7fc418a6d9457114d9a782ab86f37d02d0781ae6d3b4177b297` |
| control_registry | `f513c4017555efa486d07c3e9924944d5b0c44d2f2e76ca6e1fc934f5f718ef6` |
| controls | `a824e83e4e2e86874d6e74621ea8697eab79f167ff5662a31a437537fe829b06` |
| inspection | `c8f77902f0daedc90fb9c77ac775965d09b282ceaeea733ace8c49500ac28078` |
| layout | `fff903fd3f9f61e45cb8b9c5506df06dc366fa7980f6cb7990077cf22e938d9f` |
| profile_BR00121428 | `35d3e4062152988fd291f21e8f640bdb1d1a9560a02c90d2c3ec52c001096d52` |
| profile_BR00123523 | `6732fcbbbafe551bba3ef8be0cdc49d7c08a6d4071591e25b7b539cfb3fd8f3e` |
| qc | `34e55c0ad86d03ac31d681af03c81f55347a9dc0baac6d891e6c8fb3c54f5a98` |
| well_metadata | `fde9fe0678b8d9973f17e106e4cf7e62017110ee3b700f10e27122e1d5f291a1` |

### Archived implementation

The exact executed kit is preserved at commit
`600a38f7161079d8a11bafc0dc4073feadf1f632` in
`scripts/phase5_2_batch8_pilot/`, including its original runner, requirements and
dated authoring validation. The ten historical Python hashes below match the
approved plan. The wrapper and requirements were also verified by the publishing
helper against the original distributed kit. Later path-contract hardening in
that directory is a distinct implementation for future reviewed use; it does
not reproduce the archived code hashes or authorize rerunning the completed
pilot. See [the security review](PHASE5_2_PATH_SECURITY_REVIEW.md).

| File | SHA256 |
|---|---|
| control_utils.py | `e130a863ef8c9a98b3505380abfafbcf0e76c74e93cc10eddd3402895e6cc7c3` |
| engine.py | `1ca1dfc5d7788f2a7dab392213dd4224afe6064f42dc39657a7ef993eb88bd97` |
| pilot.py | `68e8dead8f9e82c8bd23d3c675c20f139570e0cedc4be75e121e6370b59cc9ce` |
| prepare.py | `3ce161dadf1e3f8c687bb3c0b3aeffdd1e70385e976382e5b2f7c0ef2e64faa9` |
| query_info.py | `75fddc6c4ac7edccad52972badec99817acab6241bcb971b24c63f725111adc9` |
| test_engine.py | `431855b9d75b29c61e1a2ca09b44f793000102eca5ca606fd91c571bd7de3ec5` |
| test_io.py | `39998a5c745936abdb7bc37e999fc6d9a2d32ea4c1dc6702d1a973ce592c17f0` |
| test_prepare.py | `53f0cad63311d2461bdc4948dc7eee3ff656025b7655a75e09f4faab74a47c62` |
| test_query_info.py | `0ffa687e24b31179bc31b6a39053f77a051d23016fbddb601e57f9e62fd7a17d` |
| test_run.py | `8df964da9fea7f07f3de10d28103ce4fc7a16d541821c9922e73dbefa8a0d06d` |

The runner's `P52_UV` override permits another installed uv executable. Its
original default refers to the operator's prior setup; this archive is not a
self-contained fresh-machine acquisition workflow. Preparation still requires
the previously verified local metadata/QC reports and public profile inputs.
The original authoring README/VALIDATION describe their preparation-time state;
this record documents subsequent operator execution without rewriting history.

## Validation and preservation boundary

The original authoring layout validation recorded 17 tests. A later portability
and fixture-isolation repair added a path-alias regression; the operator's pasted
Mac output records all 18 passing, public-copy consistency passing and successful
synthetic CLI checksums. Those synthetic counts are not real cohort measurements.

Pilot authoring validation recorded 45 passes and two PyArrow-dependent skips.
The publishing helper requires all 18 layout tests and all 47 pilot synthetic
tests to pass without skips in the existing Mac environments, plus the public
copy consistency check, before committing this record. That preservation check
runs no new real-data analysis. Its logs stay local. Repository CI status is
separate and must be checked on the resulting draft PR.

The standalone pilot tests require an explicit command; existing pytest discovery
is limited to `tests/` and does not automatically include the archived kit:

```bash
# Use the completed pilot's existing Python environment (contains all three pins).
PYTHONPATH=src "$PILOT_PYTHON" -m unittest discover \
  -s scripts/phase5_2_batch8_pilot -p 'test_*.py' -v
PYTHONPATH=src "$PROJECT_PYTHON" -m unittest discover \
  -s tests -p test_phase5_2_layouts.py -v
"$PROJECT_PYTHON" scripts/check_public_copy_consistency.py
```

`PILOT_PYTHON` and `PROJECT_PYTHON` are the corresponding local interpreter paths,
not committed environment definitions. The requirements file pins the pilot's
numeric dependencies. A draft PR preserves work; it does not establish that CI
passed, that collaborators approved it, or that main was updated.

## Next experiment and collaborator decisions

1. **Makenna:** select the primary manuscript question and one experiment. Retain
   this exact-label result as supporting feasibility evidence. Do not choose a
   new identity/preprocessing definition solely because it improves these scores.
2. **Claire:** evaluate shared independently supported molecular target plus
   compatible action across different compounds as a candidate relevance rule.
   Specify cell-context requirements, acceptable evidence and meaningful units.
3. **Adam:** review Broad/JCP granularity, conservative exclusions, upstream
   normalization, duplicate handling, split integrity and information leakage.
4. **Together:** approve one concrete population, query, relevance, preprocessing,
   masking, metric and failure specification before further scoring.

Biological-description queries require independently traced annotation evidence.
Using a JUMP target list for both query text and correct-answer labels is circular;
separate databases may still import the same assertions. Missing relevance is
unknown, not a verified negative. First establish eligible positive coverage
across different compounds under the candidate rule, without inspecting rankings.

A broader JCP-identity recovery experiment may be specified as a separate
sensitivity analysis. It must preserve stock ambiguities, define multiple
positives/duplicate weighting and retain the full eligible gallery. It is not a
replacement for this frozen pilot or evidence of biological retrieval.

The earlier design documents remain dated proposals. Their query-identifiability
counts (155 shared design IDs / 141 target sets) concern a different population
from these 147 retained labels. Historical CPJUMP1 results and the 13-reagent
CRISPR feasibility cohort remain separate.
