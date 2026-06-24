# Prototype

`prototype/app.py` is a minimal optional Streamlit scaffold for inspecting Phase 1 retrieval behavior. It is not required for tests.

Install optional prototype dependencies only when you want the app:

```bash
python -m pip install streamlit
```

Run:

```bash
streamlit run prototype/app.py
```

The app can load local Phase 1 manifests and queries, run lexical/random/shuffled retrieval, show perturbation-level hits, and display site metadata. Image thumbnails are shown only when local image paths exist.
