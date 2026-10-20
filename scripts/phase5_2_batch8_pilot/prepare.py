"""Deterministic, metadata-only preparation of a narrowly scoped relayout pilot."""
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from path_contract import PathContract, read_bytes, exclusive_write_json

GALLERY = "BR00123523"
QUERY = "BR00121428"
PLATES = (GALLERY, QUERY)
EXPECTED = {
    "layout": (None, "fff903fd3f9f61e45cb8b9c5506df06dc366fa7980f6cb7990077cf22e938d9f"),
    "annotation_ledger": (None, "0398a6a76910b7fc418a6d9457114d9a782ab86f37d02d0781ae6d3b4177b297"),
    "inspection": (None, "c8f77902f0daedc90fb9c77ac775965d09b282ceaeea733ace8c49500ac28078"),
    "qc": (None, "34e55c0ad86d03ac31d681af03c81f55347a9dc0baac6d891e6c8fb3c54f5a98"),
    "controls": (None, "a824e83e4e2e86874d6e74621ea8697eab79f167ff5662a31a437537fe829b06"),
    "well_metadata": (5975108, "fde9fe0678b8d9973f17e106e4cf7e62017110ee3b700f10e27122e1d5f291a1"),
    "control_registry": (740, "f513c4017555efa486d07c3e9924944d5b0c44d2f2e76ca6e1fc934f5f718ef6"),
    "profile_BR00123523": (13273070, "6732fcbbbafe551bba3ef8be0cdc49d7c08a6d4071591e25b7b539cfb3fd8f3e"),
    "profile_BR00121428": (13297459, "35d3e4062152988fd291f21e8f640bdb1d1a9560a02c90d2c3ec52c001096d52"),
}


def sha256(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def write_json(path, value):
    exclusive_write_json(path, value)


def input_limit(name):
    if name.startswith("profile_"):
        return 32 * 1024 * 1024
    if name == "well_metadata":
        return 10 * 1024 * 1024
    if name == "control_registry":
        return 64 * 1024
    return 8 * 1024 * 1024


def bound_input_bytes(paths, name, contract):
    body = contract.read_bytes(paths[name], max_bytes=input_limit(name))
    size, digest = EXPECTED[name]
    if (size is not None and len(body) != size) or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError(f"Reviewed input has changed or is missing: {name}")
    return body


def resolve_inputs(work_root):
    contract = PathContract(work_root)
    public = contract.read_pointer("latest-public-layouts")
    pair = contract.input_directory(contract.read_pointer("latest-batch8-inspection") / "inspection")
    qc = contract.input_directory(contract.read_pointer("latest-batch8-technical-qc") / "results")
    controls = contract.input_directory(contract.read_pointer("latest-batch8-controls") / "results")
    layout_root = public / "audit" if (public / "audit/layout-wells_PRIVATE.csv").is_file() else public
    paths = {"layout": layout_root / "layout-wells_PRIVATE.csv",
             "annotation_ledger": layout_root / "annotation-ledger_PRIVATE.json",
             "inspection": pair / "batch8-pair-inspection.json",
             "qc": qc / "batch8-technical-qc.json",
             "controls": controls / "batch8-control-annotations.json",
             "well_metadata": controls / "well.csv.gz",
             "control_registry": controls / "perturbation_control.csv"}
    paths.update({f"profile_{plate}": pair / f"{plate}.parquet" for plate in PLATES})
    snapshots = {}
    for name, path in paths.items():
        try:
            paths[name] = contract.input_file(path, max_bytes=input_limit(name))
            body = bound_input_bytes(paths, name, contract)
        except ValueError as exc:
            raise ValueError(f"Reviewed input has changed or is missing: {name}") from exc
        if name in ("inspection", "qc", "controls"):
            snapshots[name] = body
    inspection, qc_report, control_report = [json.loads(snapshots[name])
                                            for name in ("inspection", "qc", "controls")]
    if (qc_report["prior_inspection_sha256"] != EXPECTED["inspection"][1]
            or qc_report["layout_ledger_sha256"] != EXPECTED["layout"][1]
            or control_report["prior_qc_sha256"] != EXPECTED["qc"][1]
            or control_report["layout_sha256"] != EXPECTED["layout"][1]
            or control_report["revision"] != "016e865fa0691244e0860943e41c7d6a88ed2580"):
        raise ValueError("Reviewed report provenance links do not reconcile")
    for record in inspection["plates"]:
        name = "profile_" + record["plate"]
        if record["download"]["local_sha256"] != EXPECTED[name][1]:
            raise ValueError("Profile provenance link changed")
    for record in control_report["source_files"]:
        name = {"metadata/well.csv.gz": "well_metadata",
                "metadata/perturbation_control.csv": "control_registry"}[record["path"]]
        if (record["sha256"] != EXPECTED[name][1] or record["bytes"] != EXPECTED[name][0]
                or record["revision"] != control_report["revision"]):
            raise ValueError("Public annotation provenance link changed")
    return paths


def build_cohort(layout_by_plate, well_annotations, control_registry, observed_by_plate):
    import control_utils as utils

    if any(set(mapping) != set(PLATES) for mapping in
           (layout_by_plate, well_annotations, observed_by_plate)):
        raise ValueError("Expected exactly the two specified plates")
    layouts, annotations, observed = {}, {}, {}
    for plate in PLATES:
        def canonical_mapping(mapping):
            output = {}
            for key, value in mapping.items():
                well = utils.canonical_well(key)
                if well is None or well in output:
                    raise ValueError("Invalid or duplicate canonical well coordinates")
                output[well] = value
            return output
        layouts[plate] = canonical_mapping(layout_by_plate[plate])
        annotations[plate] = canonical_mapping(well_annotations[plate])
        original = list(observed_by_plate[plate])
        converted = [utils.canonical_well(well) for well in original]
        if None in converted or len(set(converted)) != len(original):
            raise ValueError("Invalid or duplicate observed canonical coordinates")
        observed[plate] = set(converted)
        if observed[plate] - set(layouts[plate]) or set(annotations[plate]) - set(layouts[plate]):
            raise ValueError("Observed or annotated wells lie outside the supplied layout")
    rows, broad_to_jcp, jcp_to_broad = [], defaultdict(set), defaultdict(set)
    dmso = {plate: [] for plate in PLATES}
    for plate in PLATES:
        for well, design in sorted(layouts[plate].items()):
            if "well_position" in design and utils.canonical_well(design["well_position"]) != well:
                raise ValueError("Layout row coordinate contradicts its key")
            broad, jcp = design.get("broad_sample", ""), annotations[plate].get(well)
            if not isinstance(broad, str) or (jcp is not None and not isinstance(jcp, str)):
                raise ValueError("Identifiers must be strings; missing JCP may be null")
            label = utils.classify_control(jcp, control_registry)
            reasons = []
            if design.get("included_in_key_comparison") != "True":
                reasons.append("design_not_included_treatment")
            if design.get("control_type", "").strip().lower() not in ("", "na", "n/a", "none", "nan"):
                reasons.append("design_control_label")
            if design.get("pert_type", "trt") != "trt":
                reasons.append("design_not_treatment_type")
            if not broad:
                reasons.append("missing_broad_sample")
            if well not in observed[plate]:
                reasons.append("profile_well_absent")
            if well not in annotations[plate]:
                reasons.append("production_annotation_absent")
            if label != "not_listed_in_control_registry":
                reasons.append("production_" + label)
            if label == "registered_dmso_negative_control" and well in observed[plate]:
                dmso[plate].append(well)
            if broad and isinstance(jcp, str) and re.fullmatch(r"JCP2022_[0-9]{6}", jcp):
                broad_to_jcp[broad].add(jcp)
                jcp_to_broad[jcp].add(broad)
            rows.append({"plate": plate, "well": well, "broad_sample": broad,
                         "jcp2022": jcp, "reasons": reasons})
    preliminary = [row for row in rows if not row["reasons"]]
    frequencies = {plate: {
        field: Counter(row[field] for row in preliminary if row["plate"] == plate)
        for field in ("broad_sample", "jcp2022")} for plate in PLATES}
    eligible, excluded = {plate: [] for plate in PLATES}, []
    for row in rows:
        broad, jcp, plate = row["broad_sample"], row["jcp2022"], row["plate"]
        if broad and len(broad_to_jcp[broad]) > 1:
            row["reasons"].append("broad_maps_to_multiple_jcp_ids")
        if jcp and len(jcp_to_broad[jcp]) > 1:
            row["reasons"].append("jcp_maps_to_multiple_broad_ids")
        for field in ("broad_sample", "jcp2022"):
            if frequencies[plate][field][row[field]] > 1:
                row["reasons"].append("duplicate_eligible_" + field + "_within_plate")
        if row["reasons"]:
            row["reasons"] = sorted(set(row["reasons"]))
            excluded.append(row)
        else:
            eligible[plate].append({key: value for key, value in row.items() if key != "reasons"})
    gallery, queries = eligible[GALLERY], eligible[QUERY]
    for row in queries:
        candidates = [item for item in gallery if item["well"] != row["well"]]
        row["positive_gallery_wells"] = [item["well"] for item in candidates
                                         if item["broad_sample"] == row["broad_sample"]
                                         and item["jcp2022"] == row["jcp2022"]]
        row["candidate_count"] = len(candidates)
        row["evaluable"] = bool(row["positive_gallery_wells"])
    evaluable = sum(row["evaluable"] for row in queries)
    counts = {"gallery_population": len(gallery), "query_population": len(queries),
              "evaluable_queries": evaluable, "queries_without_positive": len(queries) - evaluable,
              "query_coverage": evaluable / len(queries) if queries else None,
              "dmso_wells": {plate: len(wells) for plate, wells in dmso.items()},
              "excluded_wells": {plate: sum(row["plate"] == plate for row in excluded) for plate in PLATES},
              "exclusion_reasons_nonexclusive": dict(sorted(Counter(
                  reason for row in excluded for reason in row["reasons"]).items()))}
    return ({"schema_version": 1, "gallery_plate": GALLERY, "query_plate": QUERY,
             "gallery": gallery, "queries": queries, "dmso_wells": dmso, "exclusions": excluded}, counts)


def prepare(work_root, out):
    import control_utils as utils
    import query_info

    contract = PathContract(work_root)
    out = contract.create_output(out)
    try:
        paths = resolve_inputs(work_root)
        layouts, observed = utils.load_reviewed_inputs(paths["layout"], paths["qc"])
        registry = utils.read_control_registry(bound_input_bytes(paths, "control_registry", contract).decode("utf-8"))
        annotations = utils.read_selected_wells(paths["well_metadata"])
        cohort, counts = build_cohort(layouts, annotations, registry, observed)
        if any(counts["dmso_wells"][plate] != 64 for plate in PLATES):
            raise ValueError("Observed DMSO counts do not match the reviewed annotation evidence")
        contract.write_json(out / "cohort_LOCAL.json", cohort)
        plan = {
            "schema_version": 1, "status": "PROPOSED_NOT_APPROVED",
            "scope": "One-batch, two-plate morphology recovery of design-assigned sample labels with production-ID agreement",
            "inputs": {name: {"sha256": sha256(path), "bytes": path.stat().st_size}
                       for name, path in sorted(paths.items())},
            "code_sha256": {path.name: sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))},
            "cohort_sha256": sha256(out / "cohort_LOCAL.json"), "cohort_counts": counts,
            "plates": {"gallery": GALLERY, "query": QUERY, "source": "source_4", "batch": "2021_07_12_Batch8"},
            "selection": {"treatments": "included layout treatments only; exclude the union of layout controls and production-registry controls",
                          "identity": "exclude one-to-many Broad/JCP mappings and duplicate eligible within-plate identities",
                          "gallery": "all eligible Target1 samples, including those without a Target2 counterpart",
                          "queries": "all eligible Target2 samples; retain no-positive queries in coverage reporting",
                          "chemical_equivalence": "do not merge distinct exact IDs using standardized chemical keys"},
            "feature_inventory": {"prefixes": ["Cells_", "Cytoplasm_", "Nuclei_"], "count": 3673,
                                  "status": "proposed diagnostic inventory; Image features excluded by scope, not declared technical"},
            "preprocessing": {"fit_rows": "64 source-labeled DMSO wells on gallery plate only",
                              "center": "per-feature median", "scale": "1.4826 * median(abs(x - median(x)))",
                              "feature_mask": "finite positive MAD on gallery controls only",
                              "held_out_query_plate_fitting": False, "dtype": "float64",
                              "failure_policy": "Stop before metrics for no retained features, nonfinite transformed values, or any zero-norm eligible profile"},
            "scoring": {"method": "cosine", "direction": "Target2 queries -> Target1 gallery",
                        "positive": "exact Broad sample ID and consistent unique JCP identity",
                        "candidate_mask": "exclude identical canonical well coordinates",
                        "ties": "uniform random ordering within exactly equal float64 scores; analytic expected metrics"},
            "metrics": {"primary": "conditional mean reciprocal rank", "secondary": ["Recall@1", "Recall@5", "Recall@10"],
                        "population": "all eligible query IDs retained; no-positive queries reported separately and excluded only from conditional metric means",
                        "coverage": "evaluable / all eligible queries", "statistical_unit": "unique query reagent conditional on this plate pair",
                        "pvalues_or_resampling": False},
            "diagnostics": {"uniform_random": "per-query H_n/n expected RR and min(k,n)/n expected Recall@k with one positive",
                            "coordinate_only": "negative squared row/column grid distance, same candidate mask and tie averaging; residual-position diagnostic, not a statistical null"},
            "query_information_design": query_info.analyze(paths["layout"], paths["annotation_ledger"]),
            "query_information_population": "Shared Broad IDs in the public layout design before production-control and identity-ambiguity exclusions; not the final scored query cohort",
            "limitations": ["Design-assigned Broad IDs and public per-well JCP labels do not independently confirm reagent delivery.",
                            "Identifier ambiguity is excluded with a ledger; no chemical-key collapsing is permitted.",
                            "Eligibility requires both an included treatment layout label and an unlisted production control ID; unlisted alone is insufficient.",
                            "Distinct chemical samples retained as candidates are not asserted to be biologically unrelated negatives.",
                            "One shared batch and one plate per layout do not support independent replication or a causal layout effect.",
                            "Dose, exposure, culture independence and upstream preprocessing remain unresolved.",
                            "This phenotype-only diagnostic cannot establish language-to-biology retrieval performance."],
            "approval": "Explicit approval must bind the SHA256 of this plan.json and code/input hashes before fitting or scoring.",
            "execution_performed": False}
        # Recheck immutable sources after cohort/query derivation and before a
        # completed plan is recorded. No same-user concurrent-race proof is implied.
        for name in paths:
            bound_input_bytes(paths, name, contract)
        contract.write_json(out / "plan.json", plan)
        digest = sha256(out / "plan.json")
        contract.write_text(out / "plan.sha256", digest + "  plan.json\n")
        human_counts = [("Eligible Target1 gallery samples", counts["gallery_population"]),
                        ("Eligible Target2 query samples", counts["query_population"]),
                        ("Queries with an eligible exact-label positive", counts["evaluable_queries"]),
                        ("Queries without a positive (reported separately)", counts["queries_without_positive"]),
                        ("Target1 DMSO controls used to fit scaling", counts["dmso_wells"][GALLERY]),
                        ("Target2 DMSO controls available, not used to fit", counts["dmso_wells"][QUERY])]
        rows = "".join(f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
                       for key, value in human_counts)
        body = ("<!doctype html><meta charset='utf-8'><title>Batch8 proposed pilot</title>"
                "<style>body{font:17px system-ui;max-width:950px;margin:3em auto;line-height:1.5}"
                "td{padding:.4em;border-bottom:1px solid #ddd}pre{white-space:pre-wrap}</style>"
                "<h1>Proposed Batch8 relayout feasibility pilot</h1>"
                "<p>Metadata preparation completed. No fitting, scoring, inference or network access occurred.</p>"
                "<p>This is a phenotype-only diagnostic. The cohort and protocol require review before execution.</p>"
                f"<table>{rows}</table>"
                "<h2>What approving this pilot permits</h2><ol>"
                "<li>Use the two already-downloaded public profiles. Exclude layout/registry controls and ambiguous identities from retrieval; preserve exclusions.</li>"
                "<li>Fit median/MAD scaling on Target1 DMSO controls only. Retain the prespecified cell-compartment features with positive finite control MAD.</li>"
                "<li>Rank the full eligible Target1 gallery for each Target2 query by cosine similarity, excluding identical well coordinates.</li>"
                "<li>Calculate tie-averaged MRR and Recall@1/5/10, plus random-rank and well-position-only reference results.</li>"
                "<li>Save local tables, figures, environment details and one aggregate report. No language models, additional profile downloads, GitHub changes or public release.</li></ol>"
                "<p><strong>Interpretation:</strong> one-plate-pair design-label recovery only. Stock identity, dose/exposure, culture independence and upstream processing remain unresolved. "
                "This is not a language-retrieval result or a biological-validation experiment.</p>"
                "<p>Running the separate score command records your approval of this specific local diagnostic. It does not record collaborator approval or change a frozen benchmark.</p>"
                f"<p>Plan SHA256: <code>{digest}</code></p>"
                "<details><summary>Complete protocol, exclusions and evidence hashes</summary><pre>"
                + html.escape(json.dumps(plan, indent=2, sort_keys=True)) + "</pre></details>")
        contract.write_text(out / "REPORT.html", body)
        files = sorted(path for path in out.iterdir() if path.is_file())
        contract.write_text(out / "SHA256SUMS", "".join(f"{sha256(path)}  {path.name}\n" for path in files))
        return plan
    except Exception as exc:
        contract.write_json(out / "preparation-error.json", {"status": "INCOMPLETE", "exception": type(exc).__name__,
                                                            "message": str(exc)})
        raise
