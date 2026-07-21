# Perturb-LM Web Prototype

This app is a public-facing, synthetic interface demo for Perturb-LM. It does not run a real biomedical retrieval model and does not display real row-level data.

## Local Setup

```bash
pnpm install
pnpm run dev
```

Then open `http://localhost:3000`.

Routes:

- `/` public overview
- `/dashboard` benchmark dashboard with public-safe aggregate metrics
- `/demo` synthetic search interface
- `/methods` public-safe methods overview
- `POST /api/search` mock-provider search contract

## Checks

```bash
pnpm run lint
pnpm run typecheck
pnpm run test
pnpm run build
```

The demo search route returns deterministic synthetic results only. Keep real data, embeddings, model weights, generated indexes, and generated outputs outside this app and out of Git.
