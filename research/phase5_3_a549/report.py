"""Local scientific report for the newly supplied public four-plate cohort.

Only whitelisted aggregate values are rendered.  Private result tables supply
anonymous points and complete-eligibility counts, never text or raw-table embeds.
"""

from __future__ import annotations

from html import escape
import math
import numbers
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PRIMARY = "different_row_and_column"
SECONDARY = "different_coordinate"
MASKS = (PRIMARY, SECONDARY)
COLORS = {PRIMARY: "#7651A8", SECONDARY: "#117E83"}
LABELS = {PRIMARY: "Different row and column (primary)", SECONDARY: "Different coordinate"}
FILES = (
    "panel_a_plate_pairs.png", "panel_b_source_group_distribution.png",
    "panel_c_position_comparator.png", "panel_d_query_information.png",
    "panel_e_complete_coverage.png",
)


def _number(value):
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        result = float(value)
        return result if math.isfinite(result) else None
    return None


def _count(value):
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None


def _format(value):
    number = _number(value)
    if number is None:
        return "Unavailable"
    return str(int(number)) if number.is_integer() else f"{number:.6g}"


def _result_summary(result):
    return result.get("summary", {}) if isinstance(result, dict) and isinstance(result.get("summary"), dict) else {}


def _prepare(crossguide_result, query_result):
    cross = _result_summary(crossguide_result)
    query = _result_summary(query_result)
    masks = cross.get("masks", {})
    masks = masks if isinstance(masks, dict) else {}
    initial = cross.get("initial_noncontrol_anchors_per_plate", {})
    initial = initial if isinstance(initial, dict) else {}
    pairs, plate_names = {}, set(initial)
    for mask in MASKS:
        mask_summary = masks.get(mask)
        records = mask_summary.get("unordered_plate_pairs", []) if isinstance(mask_summary, dict) else []
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict) or "plate_a" not in record or "plate_b" not in record:
                continue
            pair = tuple(sorted((str(record["plate_a"]), str(record["plate_b"]))))
            plate_names.update(pair)
            pairs.setdefault(pair, {})[mask] = _number(record.get("contrast"))
    plate_map = {name: f"P{index + 1}" for index, name in enumerate(sorted(plate_names))}
    genes = crossguide_result.get("private_genes") if isinstance(crossguide_result, dict) else None
    observations = crossguide_result.get("private_observations") if isinstance(crossguide_result, dict) else None
    coverage = None
    required = {"mask", "anchor_plate", "row_id", "weight", "complete_pair_eligible"}
    if (initial and isinstance(masks.get(PRIMARY), dict) and isinstance(observations, pd.DataFrame)
            and required.issubset(observations.columns)):
        weights = observations.weight.map(_number)
        eligible = observations[
            observations["mask"].eq(PRIMARY)
            & observations.complete_pair_eligible.eq(True)
            & weights.map(lambda value: value is not None and value > 0)
        ]
        counts = eligible.drop_duplicates(["anchor_plate", "row_id"]).groupby("anchor_plate").size().to_dict()
        if (set(counts).issubset(initial)
                and all(_count(value) is not None and int(counts.get(plate, 0)) <= int(value) for plate, value in initial.items())):
            coverage = [(plate_map[plate], int(initial[plate]), int(counts.get(plate, 0))) for plate in sorted(initial)]
    return {"cross": cross, "query": query, "masks": masks, "pairs": pairs,
            "plate_map": plate_map, "genes": genes, "coverage": coverage}


def _eligible_genes(data, mask, *, position=False):
    frame = data["genes"]
    columns = {"mask", "contrast", "weight", "complete_pair_eligible"}
    if position:
        columns.add("position_contrast")
    if not isinstance(frame, pd.DataFrame) or not columns.issubset(frame.columns):
        return []
    result = []
    for row in frame.loc[frame["mask"].eq(mask)].to_dict("records"):
        weight, contrast = _number(row["weight"]), _number(row["contrast"])
        position_value = _number(row.get("position_contrast"))
        if row["complete_pair_eligible"] == True and weight is not None and weight > 0 and contrast is not None:
            if not position or position_value is not None:
                result.append((contrast, position_value))
    return result


def _unavailable(ax, title, reason):
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    ax.text(0.5, 0.5, "Unavailable\n" + reason, ha="center", va="center", transform=ax.transAxes,
            color="#606873", wrap=True, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_pairs(ax, data):
    title = "A  Six physical plate pairs: morphology contrast"
    pairs = sorted(data["pairs"])
    if not pairs or not any(value is not None for values in data["pairs"].values() for value in values.values()):
        _unavailable(ax, title, "No finite complete-cohort plate-pair contrasts.")
        return
    for mask, offset, marker in ((PRIMARY, -0.10, "o"), (SECONDARY, 0.10, "s")):
        values = [(index + offset, data["pairs"][pair].get(mask)) for index, pair in enumerate(pairs)]
        finite = [(x, y) for x, y in values if y is not None]
        if finite:
            ax.scatter([v[0] for v in finite], [v[1] for v in finite], color=COLORS[mask], marker=marker,
                       s=42, label=LABELS[mask], zorder=3)
    ax.axhline(0, color="#9197A1", linewidth=0.8, linestyle="--")
    ax.set_xticks(range(len(pairs)), [f"{data['plate_map'][p]}–{data['plate_map'][q]}" for p, q in pairs])
    ax.set_ylabel("Weighted cosine contrast")
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    ax.legend(frameon=False, fontsize=7, loc="best")
    ax.grid(axis="y", alpha=0.15)


def _draw_distribution(ax, data):
    title = "B  Anonymous source-annotation group contrasts"
    values = {mask: [point[0] for point in _eligible_genes(data, mask)] for mask in MASKS}
    combined = [value for group in values.values() for value in group]
    if not combined:
        _unavailable(ax, title, "No finite complete eligible source groups.")
        return
    low, high = min(combined), max(combined)
    if low == high:
        padding = max(0.01, abs(low) * 0.1)
        low, high = low - padding, high + padding
    bins = min(12, max(3, math.ceil(math.sqrt(len(combined)))))
    edges = [low + (high - low) * index / bins for index in range(bins + 1)]
    for mask in MASKS:
        if values[mask]:
            ax.hist(values[mask], bins=edges, color=COLORS[mask], alpha=0.45, edgecolor=COLORS[mask],
                    label=f"{LABELS[mask]} (n={len(values[mask])})")
    ax.axvline(0, color="#9197A1", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Within-source-group morphology contrast")
    ax.set_ylabel("Source-annotation group count")
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    ax.legend(frameon=False, fontsize=7, loc="best")
    ax.yaxis.get_major_locator().set_params(integer=True)


def _draw_scatter(ax, data):
    title = "C  Morphology and fixed-position comparator"
    points = {mask: _eligible_genes(data, mask, position=True) for mask in MASKS}
    if not any(points.values()):
        _unavailable(ax, title, "No finite complete eligible paired group values.")
        return
    for mask, marker in ((PRIMARY, "o"), (SECONDARY, "s")):
        if points[mask]:
            ax.scatter([point[1] for point in points[mask]], [point[0] for point in points[mask]],
                       color=COLORS[mask], marker=marker, alpha=0.65, s=28,
                       label=f"{LABELS[mask]} (n={len(points[mask])})", edgecolors="none")
    ax.axhline(0, color="#9197A1", linewidth=0.8, linestyle="--")
    ax.axvline(0, color="#9197A1", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Fixed-position kernel contrast (different scale)")
    ax.set_ylabel("Morphology cosine contrast")
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    ax.legend(frameon=False, fontsize=7, loc="best")


def _query_rows(data):
    descriptions = data["query"].get("descriptions", {})
    if not isinstance(descriptions, dict):
        return []
    return [(key, descriptions[key]) for key in ("category_only", "gene_aware") if isinstance(descriptions.get(key), dict)]


def _draw_query(ax, data):
    title = "D  New query-field information analogues"
    rows = _query_rows(data)
    if not rows or not any(_count(row.get("analyzed_unique_reagent_count")) for _, row in rows):
        _unavailable(ax, title, "No analyzed unique treatment reagent population.")
        return
    ax.set_axis_off()
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    left, right = ax.inset_axes([0.03, 0.16, 0.42, 0.70]), ax.inset_axes([0.58, 0.16, 0.40, 0.70])
    for index, (key, row) in enumerate(rows):
        color = COLORS[MASKS[index]]
        denominator = _count(row.get("analyzed_unique_reagent_count"))
        unique = _count(row.get("unique_signature_reagent_count"))
        entropy = _number(row.get("conditional_identity_entropy_bits"))
        if denominator and unique is not None:
            left.bar(index, unique / denominator, color=color, alpha=0.85, width=0.6)
            left.text(index, unique / denominator + 0.035, f"{unique}/{denominator}", ha="center", fontsize=8)
        if entropy is not None:
            right.bar(index, entropy, color=color, alpha=0.85, width=0.6)
            right.text(index, entropy, f"{entropy:.4g}", ha="center", va="bottom", fontsize=8)
    labels = ["Category\nonly" if key == "category_only" else "Gene\naware" for key, _ in rows]
    for inset in (left, right):
        inset.set_xticks(range(len(rows)), labels, fontsize=8)
        inset.tick_params(labelsize=8)
    left.set_ylim(0, 1.18)
    left.set_ylabel("Singleton reagent fraction", fontsize=8)
    right.set_ylabel("Conditional identity entropy (bits)", fontsize=8)
    right.margins(y=0.22)
    right.set_ylim(bottom=0)


def _draw_coverage(ax, data):
    title = "E  Primary-mask eligibility among observed treatment profiles"
    rows = data["coverage"]
    if rows is None:
        _unavailable(ax, title, "Initial plate counts or complete weighted observations unavailable.")
        return
    positions = list(range(len(rows)))
    ax.bar([x - 0.18 for x in positions], [row[1] for row in rows], width=0.36, color="#C9CDD4",
           label="Observed treatment anchors")
    ax.bar([x + 0.18 for x in positions], [row[2] for row in rows], width=0.36, color=COLORS[PRIMARY],
           label="Complete eligible anchors (positive canonical weight)")
    for index, (_, initial, eligible) in enumerate(rows):
        ax.annotate(str(initial), (index - 0.18, initial), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
        ax.annotate(str(eligible), (index + 0.18, eligible), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    ax.set_xticks(positions, [row[0] for row in rows])
    ax.set_ylabel("Unique treatment anchor wells")
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="best")
    ax.margins(y=0.18)
    ax.yaxis.get_major_locator().set_params(integer=True)


_DRAWERS = (_draw_pairs, _draw_distribution, _draw_scatter, _draw_query, _draw_coverage)
_CAPTIONS = (
    "Each point is a result for one unordered physical plate pair, using the canonical complete-cohort weights. "
    "Missing values remain unavailable. The pairs share the same four physical plates and are dependent descriptions of one cohort.",
    "One observation per finite, complete eligible recorded source-annotation group per mask. "
    "These annotations are provisional source strings, not reviewed targets or established biological equivalence classes.",
    "Anonymous source-group values use the same eligible observations and canonical weights. "
    "The fixed-position kernel and morphology cosine have different scales. No regression, subtraction, causal adjustment, or technical-cause claim is made.",
    "Bar labels give singleton-signature reagent counts over analyzed unique reagent denominators. Repeated wells do not add independent identities. "
    "These new field-signature analogues are not verified historical V1/V2 renderings. Conflict exclusions can change denominators between descriptions; "
    "such differences do not isolate the effect of adding the gene field. Literal recorded gene information can trivially help identity without biological understanding.",
    "Complete eligible coverage deduplicates anchor wells from primary-mask private observations with complete_pair_eligible=True and positive canonical weight. "
    "The initial treatment-anchor denominator contains observed profiles only; absent design wells are reported separately and are never zero-filled. "
    "It does not use raw metadata-positive/reference support as the coverage endpoint.",
)


def _cell(value, metric=None):
    attribute = f' data-metric="{escape(metric, quote=True)}"' if metric else ""
    return f"<td{attribute}>{escape(_format(value))}</td>"


def _availability(summary):
    """Whitelist aggregate counts; do not embed source identifiers or ledgers."""
    raw = summary.get("profile_availability")
    if not isinstance(raw, dict):
        return None
    keys = ("planned_physical_wells", "observed_profile_rows", "absent_profile_wells")
    values = [_count(raw.get(key)) for key in keys]
    valid = all(value is not None for value in values) and values[0] == values[1] + values[2]
    by_plate = raw.get("by_plate")
    by_plate = by_plate if isinstance(by_plate, dict) else {}
    rows = []
    for index, plate in enumerate(sorted(by_plate, key=str)):
        row = by_plate[plate]
        counts = [_count(row.get(key)) for key in keys] if isinstance(row, dict) else [None] * 3
        if not all(value is not None for value in counts) or counts[0] != counts[1] + counts[2]:
            valid = False
        rows.append((f"P{index + 1}", counts))
    if len(rows) != 4 or (valid and any(sum(row[1][index] for row in rows) != values[index] for index in range(3))):
        valid = False
    return {"raw": raw, "counts": values if valid else [None] * 3,
            "plates": rows if valid else [], "valid": valid}


def _availability_html(availability):
    if availability is None:
        return ""
    values = availability["counts"]
    html = '<section class="card"><h2>Profile availability before scoring</h2>'
    html += ("<p>Physical design positions: <strong>" + escape(_format(values[0]))
             + "</strong>; observed profiles: <strong>" + escape(_format(values[1]))
             + "</strong>; absent profile positions: <strong>" + escape(_format(values[2])) + "</strong>.</p>")
    html += ("<p>Absence has an unknown cause. It is not interpreted as a zero vector, cell death, "
             "a known QC exclusion, or random missingness. Panel E and the numerical eligibility "
             "denominators concern observed treatment profiles; the physical-grid and source-design "
             "denominators below are separate. Missing profiles can remove guides, source groups and "
             "reference candidates, so the result is conditional on the observed subset.</p>")
    if not availability["valid"]:
        return html + "<p>Availability counts are unavailable because the supplied aggregate counts are incomplete or inconsistent.</p></section>"
    body = ["<tr><th>All plates</th>" + "".join(_cell(value, f"availability-total-{key}") for key, value in zip(("planned", "observed", "absent"), values)) + "</tr>"]
    for label, counts in availability["plates"]:
        body.append("<tr><th>" + label + "</th>" + "".join(_cell(value, f"availability-{label}-{key}") for key, value in zip(("planned", "observed", "absent"), counts)) + "</tr>")
    html += '<table><caption>Physical-grid availability; anonymous plate labels</caption><thead><tr><th>Plate</th><th>Design positions</th><th>Observed profiles</th><th>Absent profiles</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"
    raw = availability["raw"]
    body = []
    for role, label in (("treatment", "Treatment"), ("control", "Control"), ("unclassified", "Unclassified source role")):
        values = []
        for field in ("planned_role_counts", "observed_role_counts", "absent_role_counts"):
            counts = raw.get(field)
            values.append(_count(counts.get(role, 0)) if isinstance(counts, dict) else None)
        body.append("<tr><th>" + label + "</th>" + "".join(_cell(value, f"availability-{role}-{key}") for key, value in zip(("planned", "observed", "absent"), values)) + "</tr>")
    html += '<table><caption>Source-design roles; absent profiles remain counted</caption><thead><tr><th>Role</th><th>Design positions</th><th>Observed profiles</th><th>Absent profiles</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"
    representations = raw.get("representation_counts")
    representations = representations if isinstance(representations, dict) else {}
    body = []
    fields = ("planned_distinct", "observed_distinct", "absent_well_distinct", "entirely_absent_distinct")
    for field, label in (("treatment_reagent_ids", "Recorded treatment reagent IDs"),
                         ("treatment_source_gene_strings", "Recorded treatment source-gene strings"),
                         ("treatment_valid_DNA_sequence_strings", "Recorded treatment DNA strings")):
        counts = representations.get(field)
        if isinstance(counts, dict):
            body.append("<tr><th>" + label + "</th>" + "".join(_cell(_count(counts.get(key)), f"representation-{field}-{key}") for key in fields) + "</tr>")
    if body:
        html += '<table><caption>Design identities retained in availability accounting</caption><thead><tr><th>Recorded source unit</th><th>In source design</th><th>Observed at least once</th><th>With any absent well</th><th>Entirely absent</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"
        html += ("<p class=note>Units with any absent well can also have an observed well. Entirely absent units remain in the source-design denominator. "
                 "Recorded gene strings and DNA strings are not reviewed biological targets, validated guides, or independent experimental units.</p>")
    control_fields = ("planned_control_class_counts", "observed_control_class_counts", "absent_control_class_counts")
    if all(isinstance(raw.get(field), dict) for field in control_fields):
        known = (("negcon", "Negative control"), ("poscon_cp", "Compound positive control"),
                 ("poscon_diverse", "Diverse positive control"), ("poscon_orf", "ORF positive control"))
        known_keys = {key for key, _ in known}
        body = []
        for key, label in known:
            counts = [_count(raw[field].get(key, 0)) for field in control_fields]
            body.append("<tr><th>" + label + "</th>" + "".join(_cell(value) for value in counts) + "</tr>")
        others = []
        for field in control_fields:
            counts = [_count(value) for key, value in raw[field].items() if key not in known_keys]
            others.append(sum(counts) if all(value is not None for value in counts) else None)
        body.append("<tr><th>Other or unresolved source control classes</th>" + "".join(_cell(value) for value in others) + "</tr>")
        html += '<table><caption>Source control-class availability</caption><thead><tr><th>Source control class</th><th>Design positions</th><th>Observed profiles</th><th>Absent profiles</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"
    return html + "</section>"


def _tables(data):
    fragments = []
    if data["pairs"]:
        body = []
        for pair in sorted(data["pairs"]):
            label = "–".join(data["plate_map"][plate] for plate in pair)
            body.append("<tr><th>" + label + "</th>" + "".join(_cell(data["pairs"][pair].get(mask)) for mask in MASKS) + "</tr>")
        fragments.append("<table><caption>Observed morphology cosine contrasts by physical pair</caption><thead><tr><th>Anonymous pair</th><th>Primary mask</th><th>Different coordinate</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")
    body = []
    for mask in MASKS:
        values = data["masks"].get(mask)
        if isinstance(values, dict):
            body.append("<tr><th>" + LABELS[mask] + "</th>" + "".join(_cell(values.get(field)) for field in ("contrast", "position_contrast", "eligible_gene_groups", "complete_guide_pairs", "eligible_observations")) + "</tr>")
    if body:
        fragments.append("<table><caption>Complete-cohort aggregate results</caption><thead><tr><th>Mask</th><th>Morphology contrast</th><th>Position contrast</th><th>Eligible source groups</th><th>Complete guide pairs</th><th>Eligible observations</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")
    body = []
    for key, row in _query_rows(data):
        name = "Category only" if key == "category_only" else "Gene aware"
        body.append("<tr><th>" + name + "</th>" + "".join(_cell(row.get(field), f"query-{key}-{field}") for field in (
            "distinct_signature_count", "unique_signature_reagent_count", "analyzed_unique_reagent_count",
            "excluded_conflicting_unique_reagent_count", "conditional_identity_entropy_bits",
            "tie_only_expected_exact_identity_hit_at_1")) + "</tr>")
    if body:
        fragments.append("<table><caption>Observed field-signature information</caption><thead><tr><th>New description</th><th>Distinct signatures</th><th>Singleton reagents</th><th>Analyzed reagents</th><th>Conflicting reagents excluded</th><th>Conditional entropy, bits</th><th>Tie-only identity reference</th></tr></thead><tbody>" + "".join(body) + "</tbody></table><p class=note>The tie-only reference assumes uniform weighting of analyzed unique reagents and uniform random choice within each signature class. It is an informational reference, not a retrieval score or an upper bound for an arbitrary learned task.</p>")
    if data["coverage"] is not None:
        body = ["<tr><th>" + plate + "</th>" + _cell(initial, f"coverage-{plate}-initial") + _cell(eligible, f"coverage-{plate}-complete") + "</tr>" for plate, initial, eligible in data["coverage"]]
        fragments.append("<table><caption>Primary-mask observed and complete eligible treatment anchors</caption><thead><tr><th>Anonymous plate</th><th>Observed treatment anchors</th><th>Complete eligible anchors</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")
    paired = data["cross"].get("paired_mask_difference")
    if isinstance(paired, dict):
        fragments.append("<p>Paired descriptive mask sensitivity, secondary minus primary on the complete source-group intersection: morphology contrast difference <strong>" + escape(_format(paired.get("contrast_difference"))) + "</strong>; intersection source groups <strong>" + escape(_format(paired.get("intersection_gene_groups"))) + "</strong>; intersection groups with changed complete guide pairs <strong>" + escape(_format(paired.get("intersection_genes_with_changed_complete_guide_pairs"))) + "</strong>.</p>")
    return "\n".join(fragments)


def render_report(out: Path, summary: dict, crossguide_result: dict | None, query_result: dict | None) -> None:
    """Write report.html, five relative PNGs, and a vector report.pdf into out.

    ``out`` must already exist.  No network access, model execution, inference,
    renderer invocation, raw-table embedding or source-identity labeling occurs.
    Unavailable analysis portions produce explicitly unavailable panels.
    """
    out = Path(out)
    if not out.is_dir():
        raise ValueError("Report output directory must already exist.")
    figures = out / "figures"
    figures.mkdir(exist_ok=True)
    data = _prepare(crossguide_result, query_result)
    availability = _availability(summary)
    status = str(summary.get("status", "Unavailable"))
    commit = str(summary.get("source_commit", "Unavailable"))
    style = {"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
             "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42,
             "savefig.facecolor": "white", "axes.labelcolor": "#26303B", "text.color": "#26303B"}
    with plt.rc_context(style):
        for drawer, name in zip(_DRAWERS, FILES):
            fig, ax = plt.subplots(figsize=(9.0, 4.8))
            drawer(ax, data)
            fig.savefig(figures / name, dpi=300, bbox_inches="tight")
            plt.close(fig)
        fig = plt.figure(figsize=(12, 13))
        grid = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.8], hspace=0.43, wspace=0.34)
        axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]),
                fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1]), fig.add_subplot(grid[2, :])]
        for drawer, ax in zip(_DRAWERS, axes):
            drawer(ax, data)
        fig.suptitle("Phase 5.3 · A549 four-plate exploration", x=0.08, ha="left", fontsize=16, fontweight="bold", y=0.985)
        fig.text(0.08, 0.952, "Provisional recorded source-annotation endpoint · descriptive results · upstream fit unverified", fontsize=9)
        availability_note = "Eligibility is conditional on observed profiles; absent wells are not zero-filled."
        if availability is not None:
            planned, observed, absent = availability["counts"]
            availability_note = (f"Profiles: {_format(observed)} observed / {_format(planned)} physical design positions; "
                                 f"{_format(absent)} absent. Absence cause unknown; panel E uses observed anchors.")
        fig.text(0.08, 0.04, availability_note + "\nSix plate pairs share four physical plates; no independent-experiment inference, confidence intervals or p-values.\n"
                 "Position and morphology scales differ; no causal adjustment. Query analogues are not historical V1/V2.\n"
                 "Source annotations are not reviewed targets. This public cohort does not verify the earlier private twelve-plate cohort.", fontsize=8, linespacing=1.5)
        fig.text(0.08, 0.013, f"Status: {status}    Source commit: {commit}", fontsize=7)
        fig.subplots_adjust(left=0.08, right=0.97, bottom=0.12, top=0.92)
        fig.savefig(out / "report.pdf", bbox_inches="tight", metadata={"Title": "Phase 5.3 A549 four-plate exploratory scientific panels", "Author": "", "Subject": "Descriptive provisional source-annotation analysis"})
        plt.close(fig)

    panels = "\n".join(f'<figure><img src="figures/{name}" alt="Scientific panel {chr(65 + index)}"><figcaption>{escape(caption)}</figcaption></figure>' for index, (name, caption) in enumerate(zip(FILES, _CAPTIONS)))
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Phase 5.3 A549 four-plate exploration</title><style>
body{font-family:system-ui,sans-serif;color:#26303b;background:#f5f6f8;margin:0;line-height:1.55}main{max-width:1140px;margin:auto;padding:32px 28px 64px}h1{line-height:1.15;color:#563580}h2{margin-top:2em;color:#265c62}figure,section.card{background:white;border:1px solid #dce0e5;border-radius:10px;padding:20px;margin:24px 0}img{width:100%;height:auto}figcaption,.note{font-size:.9rem;color:#525c68}table{border-collapse:collapse;width:100%;background:white;margin:24px 0;font-size:.88rem}caption{text-align:left;font-weight:650;padding:10px 0}th,td{padding:9px 10px;text-align:left;border-bottom:1px solid #dce0e5}thead{background:#eee8f5}code{overflow-wrap:anywhere}a{color:#117e83}strong{font-variant-numeric:tabular-nums}.status{color:#563580;font-weight:650}@media(max-width:720px){main{padding:18px}table{display:block;overflow-x:auto}}
</style></head><body><main><h1>A549 four-plate exploration</h1>"""
    html += f'<p class="status">Status: {escape(status)}</p><p>Source commit: <code>{escape(commit)}</code> · <a href="report.pdf">Download the scientific panels as PDF</a></p>'
    html += """<section class="card"><p>This authorized exploratory endpoint compares morphology cosine similarity for different recorded DNA strings sharing a usable recorded source-gene string, against other recorded source-gene strings. It does not establish reviewed target identities, guide equivalence, or biological understanding.</p>
<p>This A549 context extension was selected after the completed U2OS exploration. It is within the same source batch, not an independent-batch replication or an isolated causal cell-type comparison. It does not verify the earlier private twelve-plate cohort or recompute the frozen historical 641 queries. The six physical plate pairs reuse four plates; they are not six independent experiments or independent projects. No confidence intervals or p-values are reported.</p>
<p>The supplied processed vectors' upstream fitting provenance is unverified. Results describe the finite complete eligible source-annotation cohort only. Controls provide quality accounting, not treatment anchors. Unavailable numerical results remain explicitly unavailable.</p></section>"""
    html += _availability_html(availability)
    html += panels + "<h2>Numerical results and denominators</h2>" + _tables(data)
    html += """<section class="card"><p>Spatial-mask changes can alter positive wells, reference wells, reference guides, complete guide pairs and eligible source groups. Even paired differences on an intersecting source-group cohort are descriptive sensitivity results, not a causal position effect or layout-adjusted morphology effect.</p><p>Source annotations, reagent identifiers, DNA strings, guide hashes, wells and row identifiers are not embedded in this report. Private raw tables remain separate. Plate labels are anonymous and consistent across panels.</p></section></main></body></html>"""
    (out / "report.html").write_text(html, encoding="utf-8")


__all__ = ["render_report"]
