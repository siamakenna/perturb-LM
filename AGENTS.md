# Agent Instructions

These instructions apply to coding agents and automated contributors.

Perturb-LM is a leakage-aware benchmark and public synthetic prototype for natural-language retrieval over Cell Painting perturbation profiles. The validated identifier-stripped TF-IDF baseline is the current scientific reference. Learned biomedical model results remain pending.

Before changing modeling, evaluation, or public scientific text, read `docs/CLAIMS_LADDER.md`, `docs/EVALUATION_PROTOCOL.md`, and `docs/PHASE3C_TEXT_PROFILE_ALIGNMENT.md`.

Agents must preserve the distinction between synthetic checks and scientific results, run relevant tests, keep generated files in ignored directories, and make small issue-linked changes.

Agents must not download large or restricted data without explicit instruction; commit data, embeddings, caches, weights, credentials, or private paths; change benchmark definitions without an approved issue; connect the public site to real model outputs without review; publish, merge, release, or alter repository settings autonomously.
