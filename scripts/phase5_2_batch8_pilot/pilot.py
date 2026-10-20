#!/usr/bin/env python3
"""Prepare, then explicitly approve and run one public Batch8 feasibility pilot."""
import argparse
import hashlib
import html
import io
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from path_contract import PathContract, exclusive_write_bytes, exclusive_write_json, exclusive_write_text, read_bytes

SCHEMA_SHA = 'd75e6ce7741f5a50af7947ed75fb4e1555b3567635ca9b498c75e5e709efdce2'
PREFIXES = ('Cells_', 'Cytoplasm_', 'Nuclei_')


def digest(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def write_json(path, obj):
    exclusive_write_json(path, obj)


def checksums(out, contract=None, pending_summary=None):
    if contract is not None:
        out = contract.input_directory(out, within=contract.outputs)
    files = sorted(p for p in Path(out).iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    entries = {p.name: digest(p) for p in files}
    if pending_summary is not None:
        if not isinstance(pending_summary, bytes) or 'pilot-summary.json' in entries:
            raise ValueError('Completion summary must be new bytes not yet published')
        entries['pilot-summary.json'] = hashlib.sha256(pending_summary).hexdigest()
    text = ''.join(f'{entries[name]}  {name}\n' for name in sorted(entries))
    if contract is None:
        exclusive_write_text(Path(out) / 'SHA256SUMS', text)
    else:
        contract.write_text(Path(out) / 'SHA256SUMS', text)
    for path in files:
        if digest(path) != entries[path.name]:
            raise ValueError('Output checksum verification failed before completion')


def load_plate(path, plate, expected_rows, expected_schema=SCHEMA_SHA, expected_features=3673):
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from control_utils import canonical_well
    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    records = [{'name': f.name, 'type': str(f.type)} for f in schema]
    actual = hashlib.sha256(json.dumps(records).encode()).hexdigest()
    if actual != expected_schema or pf.metadata.num_rows != expected_rows:
        raise ValueError('Profile schema or row count changed')
    meta = pf.read(columns=['Metadata_Source', 'Metadata_Plate', 'Metadata_Well'], use_threads=False).to_pydict()
    wells = [canonical_well(w) for w in meta['Metadata_Well']]
    if (None in wells or len(set(wells)) != len(wells)
            or any(v != 'source_4' for v in meta['Metadata_Source'])
            or any(v != plate for v in meta['Metadata_Plate'])):
        raise ValueError('Profile metadata identity or well uniqueness failed')
    features = [f.name for f in schema if f.name.startswith(PREFIXES)]
    if len(features) != expected_features or any(not (pa.types.is_floating(schema.field(n).type)
            or pa.types.is_integer(schema.field(n).type)) for n in features):
        raise ValueError('Unexpected morphology feature inventory')
    table = pf.read(columns=features, use_threads=False)
    matrix = np.column_stack([np.asarray(table[name].to_pylist(), dtype=np.float64) for name in features])
    if not np.isfinite(matrix).all():
        raise ValueError('Nonfinite numeric profile values')
    return wells, features, matrix


def make_figure(summary, rows, out, contract=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    methods = [('morphology', 'Morphology', '#156082'),
               ('well_position_only', 'Well position only', '#b96928'),
               ('uniform_random_expectation', 'Uniform-rank reference', '#737373')]
    fields = ['reciprocal_rank', 'recall_at_1', 'recall_at_5', 'recall_at_10']
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), layout='constrained')
    x = np.arange(4)
    values = summary['metrics_conditional_on_evaluability']
    for i, (key, label, color) in enumerate(methods):
        axes[0].bar(x + (i - 1) * .25, [values[key][f] for f in fields], width=.24, label=label, color=color)
    axes[0].set_xticks(x, ['MRR', 'Recall@1', 'Recall@5', 'Recall@10'])
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel('Conditional mean over evaluable sample IDs')
    valid = [r for r in rows if r['status'] == 'evaluable']
    ks = list(range(1, min(50, max(r['candidate_count'] for r in valid)) + 1))
    for key, label, color in methods:
        y = []
        for k in ks:
            vals = []
            for row in valid:
                if key == 'uniform_random_expectation':
                    vals.append(min(k, row['candidate_count']) / row['candidate_count'])
                else:
                    m = row[key]
                    vals.append(max(0, min(m['tie_size'], k - m['rank_best'] + 1)) / m['tie_size'])
            y.append(sum(vals) / len(vals))
        axes[1].plot(ks, y, label=label, color=color)
    axes[1].set(xlabel='Retrieval depth k', ylabel='Tie-averaged Recall@k', ylim=(0, 1))
    axes[1].legend(frameon=False, fontsize=8)
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle(f"One-pair design-label recovery: {len(valid)}/{summary['query_count']} queries evaluable", fontsize=12)
    for format_name in ('png', 'svg'):
        buffer = io.BytesIO()
        fig.savefig(buffer, format=format_name, dpi=180)
        path = out / ('retrieval-summary.' + format_name)
        if contract is None:
            exclusive_write_bytes(path, buffer.getvalue())
        else:
            contract.write_bytes(path, buffer.getvalue())
    plt.close(fig)


def score(work_root, plan_dir, approval, out):
    # Check approval before importing numeric libraries or reading profile values.
    import prepare as prep
    contract = PathContract(work_root)
    plan_dir = contract.input_directory(plan_dir, within=contract.outputs)
    out = contract.fresh_output(out, forbidden=(plan_dir,))
    plan_bytes = contract.read_bytes(plan_dir / 'plan.json', max_bytes=1024 * 1024, within=plan_dir)
    if not approval or hashlib.sha256(plan_bytes).hexdigest() != approval:
        raise ValueError('Approval must equal the SHA256 of the reviewed plan.json')
    cohort_bytes = contract.read_bytes(plan_dir / 'cohort_LOCAL.json', max_bytes=8 * 1024 * 1024, within=plan_dir)
    plan = json.loads(plan_bytes)
    cohort = json.loads(cohort_bytes)
    # Recreate the entire preparation, including code/input bindings, before scoring.
    with tempfile.TemporaryDirectory(prefix='pilot-recheck-', dir=out.parent) as temporary:
        fresh_dir = Path(temporary) / 'plan'
        prep.prepare(work_root, fresh_dir)
        fresh_plan = contract.read_bytes(fresh_dir / 'plan.json', max_bytes=1024 * 1024, within=fresh_dir)
        if hashlib.sha256(fresh_plan).hexdigest() != approval:
            raise ValueError('Inputs, implementation, or proposed contract changed; regenerate and review the plan')
        fresh_cohort = contract.read_bytes(fresh_dir / 'cohort_LOCAL.json', max_bytes=8 * 1024 * 1024, within=fresh_dir)
        if hashlib.sha256(fresh_cohort).digest() != hashlib.sha256(cohort_bytes).digest():
            raise ValueError('Prepared cohort differs from its rederived contents')
    paths = prep.resolve_inputs(work_root)
    gallery_plate, query_plate = cohort['gallery_plate'], cohort['query_plate']
    profile_paths = {plate: contract.input_file(paths['profile_' + plate])
                     for plate in (gallery_plate, query_plate)}
    profile_hashes = {plate: prep.EXPECTED['profile_' + plate][1]
                      for plate in profile_paths}
    for plate, path in profile_paths.items():
        if digest(path) != profile_hashes[plate]:
            raise ValueError('Profile bytes differ from the reviewed input binding')
    import numpy as np
    import pyarrow as pa
    import matplotlib
    from engine import fit_controls, transform, evaluate
    # Recheck after preparation; no temporary/output directory may redirect this run.
    contract.create_output(out, forbidden=(plan_dir,))
    try:
        gw, features, gx = load_plate(profile_paths[gallery_plate], gallery_plate, 384)
        qw, qfeatures, qx = load_plate(profile_paths[query_plate], query_plate, 383)
        if features != qfeatures: raise ValueError('Ordered feature names disagree')
        gindex, qindex = {w:i for i,w in enumerate(gw)}, {w:i for i,w in enumerate(qw)}
        controls = cohort['dmso_wells'][gallery_plate]
        if len(controls) != 64: raise ValueError('Expected exactly 64 reference DMSO controls')
        center, scale, keep = fit_controls(gx[[gindex[w] for w in controls]])
        convert = lambda r: {'plate': r['plate'], 'well_position': r['well'],
                             'broad_sample': r['broad_sample'], 'jcp_id': r['jcp2022']}
        gallery, queries = [convert(r) for r in cohort['gallery']], [convert(r) for r in cohort['queries']]
        if not gallery or not queries: raise ValueError('No eligible gallery or queries')
        gv = transform(gx[[gindex[r['well_position']] for r in gallery]], center, scale, keep)
        qv = transform(qx[[qindex[r['well_position']] for r in queries]], center, scale, keep)
        summary, rows = evaluate(gallery, queries, gv, qv)
        if summary['evaluable_query_count'] == 0: raise ValueError('No evaluable exact-design matches')
        # Assert the scoring masks match the score-blind preparation.
        for record, result in zip(cohort['queries'], rows):
            if record['candidate_count'] != result['candidate_count'] or bool(record['evaluable']) != (result['status'] == 'evaluable'):
                raise ValueError('Scoring coverage differs from preparation')
        # Parsed matrices are already in memory. Refuse completion if their bound
        # input files changed during loading/evaluation.
        for plate, path in profile_paths.items():
            contract.input_file(path)
            if digest(path) != profile_hashes[plate]:
                raise ValueError('Profile bytes changed during scoring')
        summary.update(status='COMPLETED_DESCRIPTIVE_DESIGN_LABEL_PILOT', plan_sha256=approval,
            created_utc=datetime.now(timezone.utc).isoformat(),
            approval='operator supplied exact reviewed plan SHA256 to score command',
            scoring_performed=True, pretrained_inference_performed=False,
            fields_before_reference_mad_filter=len(features), fields_after_reference_mad_filter=int(keep.sum()),
            dropped_nonpositive_or_nonfinite_reference_mad=int((~keep).sum()),
            target_plate_used_to_fit_preprocessing=False, source_upstream_fit_scope='unverified',
            scope=plan['scope'], limitations=plan['limitations'],
            environment={'python': platform.python_version(), 'numpy': np.__version__, 'pyarrow': pa.__version__,
                         'matplotlib': matplotlib.__version__, 'platform': platform.platform()})
        contract.write_json(out / 'per-query_LOCAL.json', rows)
        contract.write_json(out / 'fitted-preprocessing_LOCAL.json', {
            'fit_plate': gallery_plate, 'fit_wells': controls,
            'feature_names': features, 'center': center.tolist(), 'scale': scale.tolist(), 'retained': keep.tolist()})
        contract.write_json(out / 'approved-plan.json', plan)
        make_figure(summary, rows, out, contract)
        metric_rows = ''.join('<tr><td>' + html.escape(method) + '</td>' + ''.join(
            f'<td>{metrics[key]:.4f}</td>' for key in ('reciprocal_rank','recall_at_1','recall_at_5','recall_at_10')) + '</tr>'
            for method, metrics in summary['metrics_conditional_on_evaluability'].items())
        limitations = ''.join('<li>' + html.escape(str(x)) + '</li>' for x in plan['limitations'])
        contract.write_text(out / 'REPORT.html', '<!doctype html><meta charset="utf-8"><title>Batch8 pilot results</title>'
            '<style>body{font:17px/1.5 system-ui;max-width:1050px;margin:40px auto;padding:0 20px}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}img{max-width:100%}</style>'
            '<h1>One-pair morphology recovery pilot</h1><p>Descriptive results; no language model or biological relationship validation.</p>'
            f'<p>Evaluable queries: <strong>{summary["evaluable_query_count"]}/{summary["query_count"]}</strong>. '
            f'Full eligible gallery: {summary["gallery_count"]}. Retained features: {int(keep.sum())}/{len(features)}.</p>'
            '<table><tr><th>Method</th><th>MRR</th><th>Recall@1</th><th>Recall@5</th><th>Recall@10</th></tr>' + metric_rows + '</table>'
            '<p>Metrics condition on having an eligible positive. Queries without positives are counted separately and excluded from conditional metric means.</p>'
            '<img src="retrieval-summary.png" alt="Descriptive retrieval comparison"><h2>Interpretation limits</h2><ul>' + limitations + '</ul>'
            '<p>Share only pilot-summary.json and, if useful, the aggregate figure. Keep LOCAL files on your computer.</p>')
        summary_bytes = (json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
        # Hash the pending summary alongside the completed outputs, verify those
        # files, and publish the completion summary only after that succeeds.
        checksums(out, contract, pending_summary=summary_bytes)
        contract.write_bytes(out / 'pilot-summary.json', summary_bytes)
        return summary
    except Exception as exc:
        contract.write_json(out / 'FAILED.json', {'status':'INCOMPLETE_DO_NOT_INTERPRET_PARTIAL_RESULTS', 'error': str(exc)})
        raise


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('score')
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--plan-dir', type=Path, required=True)
    p.add_argument('--approve-plan-sha256', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        import prepare
        prepare.prepare(args.work_root, args.out)
        print('PREPARED: no scoring. Review:', args.out / 'REPORT.html')
        print('Plan SHA256:', digest(args.out / 'plan.json'))
    else:
        summary = score(args.work_root, args.plan_dir, args.approve_plan_sha256, args.out)
        print('COMPLETE:', args.out / 'REPORT.html')
        print('Return aggregate file:', args.out / 'pilot-summary.json')
        print('Evaluable queries:', summary['evaluable_query_count'])


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'STOP: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
