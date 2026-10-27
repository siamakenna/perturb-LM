# Perturb-LM: 27 October 2026 continuation

This is a runnable transfer kit, not a full repository or a research-data bundle.
It includes a development flowchart, an evidence register, a completion tracker,
and three parallel readiness jobs. `--fetch-source` copies the two recorded public
source revisions into separate local checkouts. Downloaded project/model source
is not executed by the preflight. No weights or research datasets are downloaded.

## What is complete

- PR92: A549 exploratory source, last terminal-verified at
  `c28bd56f56771055e3cc5c7e84bcff0841e76190`; nine reported successful checks and
  one skipped manual check.
- PR93: context methods, tests, focused CI and a multichannel proposal, repaired
  at `88d367fa7c7ea224af14de979efcb1831d3518d6`; fifteen reported successful
  checks, one skipped and no failures or pending checks. The repair changed only
  SciPy to 1.15.3 and scikit-image to 0.25.2 in the pinned package cohort.
- Completed exploratory U2OS/A549 profile analyses and a post hoc agreement
  diagnostic are preserved in the supplied history. The current kit does not
  independently reverify their raw profile files or rerun scoring.
- Available aggregate summaries establish a bounded production Batch8 pilot and
  separate MOA analyses. See `batch_usage_notes.md` for scope and caveats.

No PR merge is established by the publication helper. A later PR state must be
read afresh. Software CI is not biological validation.

## Are the new batches being used?

Some expansion data have been used. Three additional A549 plates were analyzed
alongside BR00117000, all in the original `2020_11_04_CPJUMP1` batch. Separately,
the bounded cpg0016 source_4 / `2021_07_12_Batch8` Target1/Target2 profile pilot
was completed. These are different exploratory questions. No independent
multibatch ChAda-ViT experiment or cross-batch language-generalization result
has been established.

The ten previously downloaded fluorescence TIFFs represent two compound sites,
not the matched CRISPR image cohort. The new inventory verifier can check those
bytes and five-channel grouping. It does not decode pixels, verify registration,
or establish image quality or biological relevance.

## What the next jobs actually do

| Job | Action | Completion evidence |
| --- | --- | --- |
| GitHub/source | Read current main and PR92/93 state; optionally copy both pinned public source revisions | Current-head observations, source commit checks and clean detached checkouts |
| Local evidence | Check known aggregate-summary hashes and the reviewed local image inventory | Available/missing evidence and byte-integrity results; private path ledger stays local |
| Model source | Capture author source and checkpoint metadata/text source at observed revisions | Source pins and hashes; unresolved license, training overlap and integration review remain explicit |

These jobs run concurrently on up to three worker threads and update
`tracker.json` as each finishes. A missing input records a blocker; other jobs
continue. Historical scientific completions are not promoted to recipient-side
verification by a successful software check.

## Run on a Mac

Python 3.9 or newer is sufficient; no new Python packages are needed. GitHub CLI
and Git are needed for the public-source jobs. On a computer without `gh`, those
jobs will record blockers while the local inventory job can still run.

From this extracted kit directory:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 run_parallel_preflight.py --out /path/to/a/new/folder --fetch-source
```

The output folder must not already exist; its parent must exist. In the supplied
chat command, a fresh parent is created and `results` is the new output folder.
Use `--downloads` to inspect a different, explicitly selected Downloads directory.
No remote computer is assumed reachable. Missing original-Mac data remain missing.

Open the generated `REPORT.html` and inspect `tracker.json`. The two project
source checkouts, when copied, are under `source/PR92` and `source/PR93` in the
run folder. They preserve separate unmerged workstreams; no merge is inferred.
The transfer kit alone does not contain those full source repositories.

## Save the new readiness source to GitHub

After the source job obtains the clean pinned PR93 checkout, run:

```bash
python3 publish_handoff.py --source-repo /path/to/run/source/PR93 --publish --watch-checks
```

The publisher verifies package hashes and reruns the readiness synthetic tests.
It creates a fresh worktree and a new branch, commits only the twenty-two named
handoff files (including the checksum list), pushes without force and verifies the new draft PR's
head. The PR is based on PR93's branch, retaining the repaired package cohort
without changing PR92 or PR93. If PR93 has changed or closed, the publisher
stops for source reconciliation. No existing PR is merged or retargeted.

The publisher records a local receipt and a resume pointer beside the source
clone. Repeating the same command resumes its recorded publication folder.
With `--watch-checks`, the helper waits for reported GitHub checks and rechecks
the saved head. A successful push remains separate from passing CI. This copy step publishes no run outputs,
source clones, raw images, research rows or private logs.

## ChAda-ViT selection and compatibility

ChAda-ViT/16 Moyen is a proposed candidate, not an integrated model. It uses
DINO-style self-supervision, not specifically DINOv2. The source audit found
that channel grouping, token-versus-image output, and an isolated software
runtime need explicit decisions. See `model_public_audit.md` and
`model_readiness.md`. No custom model source is imported or executed here.

After the three readiness streams converge, freeze one cohort and one
full-channel versus reduced-channel comparison with a matched CellProfiler
reference. Keep repeated wells and overlapping plate pairs separate from
independent biological units. Language alignment and query relevance require
a later, separate experiment. Do not select only favorable development groups.

## Files and sharing

`READ_FIRST.html` provides an offline overview and the flowchart.
`tracker_seed.json` preserves the starting task evidence. `VALIDATION.json`
records only checks actually executed while preparing this kit.

Generated `LOCAL_PATHS_PRIVATE.json`, private job logs, raw images, profile files
and research row tables remain local. The separate source-publication helper
copies an explicit source/documentation whitelist; it never includes run outputs.
The delivered kit is a new artifact and is not itself claimed to have been
pushed from this conversation. Existing completed research source is verified
on PR92/93 as above.

No collaborator contact, Biowulf computation, model download, inference,
scientific scoring, release, deployment or PR merge occurs in this preflight.

## Publication correction and current source-Mac state

The supplied 27 October terminal output reports all 46 original synthetic tests
and all three concurrent readiness checks completed. The original publisher
stopped before committing because the repository ignores PNG files and its
scope check omitted the reviewed flowchart. This revision accounts for ignored
files only within the fixed, checksum-verified whitelist, explicitly stages
that list, and retains the exact staged-scope and content checks. Three new
regression tests passed; the corrected suite contains 49 tests.

A separate publication-fix launcher preserves the stopped worktree and resumes
publication from a fresh sibling worktree after checking the stopped branch was
not published. No scientific rerun is needed for this correction. Successful
publication and CI must still be confirmed by the source Mac's new receipt.

Biowulf access is not required for a receiving-device handoff or source work.
Source/checkpoint review, isolated-runtime design and synthetic adapter tests
can proceed locally. Real-image experiments still require the actual selected
image cohort, verified preprocessing and a frozen evaluation design.
