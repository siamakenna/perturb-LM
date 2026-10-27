# Local runbook

1. Save the delivered ZIP in Downloads and verify its outer SHA-256 using the
   value provided in the conversation. Extract into a fresh directory.
2. From the kit directory, run `shasum -a 256 -c SHA256SUMS` and then
   `python3 -m unittest discover -s . -p 'test_*.py' -v`.
3. Run `python3 run_parallel_preflight.py --out /existing/parent/new-results
   --fetch-source`. The destination must not already exist. The three readiness
   jobs run concurrently and keep reporting independent completion/blocker states.
4. Open the generated REPORT.html and inspect tracker.json. The main GitHub
   snapshot, two clean pinned source copies, local availability summary, and
   model-source observations are separate outputs. Missing data are not failures
   of a scientific hypothesis.
5. If the source job completed, publish the new reviewed readiness source with
   `python3 publish_handoff.py --source-repo /path/to/results/source/PR93
   --publish --watch-checks`. The new draft PR is stacked on PR93 and preserves existing PRs.
   Record its printed URL, remote SHA and final check status.
6. Preserve the run folder. Detailed path ledgers and private error logs remain
   local. No profile scoring or model inference is part of these commands.

On a second Mac without the research files, the local-evidence job should report
missing inputs. The GitHub and model-source jobs can still finish if Git, gh,
curl and network access are available. The runner does not request or transfer
private data from the original Mac.

Do not reinstall an author's older model environment into the existing
Perturb-LM environment. Runtime selection, channel grouping, fixed-vector output,
preprocessing and training overlap remain explicit work before inference.

If the original publication stopped at "Only reviewed readiness files may be
committed", use the separate publication-fix launcher. It preserves the original
worktree and all outputs. Do not bypass the guard with a broad git add command.
The corrected source helper can explicitly stage only its reviewed PNG/JSON
files even when repository or global ignore rules match those extensions.
