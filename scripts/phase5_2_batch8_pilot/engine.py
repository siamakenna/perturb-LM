"""Small, prespecified morphology-recovery baseline; no language model."""
import math
import numpy as np

KS = (1, 5, 10)


def fit_controls(controls):
    """Median / normal-consistent MAD, using reference-plate DMSO only."""
    x = np.asarray(controls, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] < 2 or not np.isfinite(x).all():
        raise ValueError('Expected a finite reference-control matrix')
    center = np.median(x, axis=0)
    scale = 1.4826 * np.median(np.abs(x - center), axis=0)
    keep = np.isfinite(scale) & (scale > 0)
    if not keep.any():
        raise ValueError('No features have positive reference-control MAD')
    return center, scale, keep


def transform(x, center, scale, keep):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != len(center) or not np.isfinite(x).all():
        raise ValueError('Unexpected/nonfinite profile matrix')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        z = (x[:, keep] - center[keep]) / scale[keep]
        # Normalize stably without changing the cosine direction.
        largest = np.max(np.abs(z), axis=1)
        if not np.isfinite(z).all() or not np.isfinite(largest).all() or (largest == 0).any():
            raise ValueError('Nonfinite or zero transformed vector; no scores were accepted')
        z = z / largest[:, None]
        norm = np.sqrt(np.sum(z * z, axis=1))
        z = z / norm[:, None]
    if not np.isfinite(z).all():
        raise ValueError('Nonfinite normalized vector')
    return z


def tie_metrics(scores, positive):
    """Expected one-positive metrics over uniform ordering within exact ties."""
    a = np.asarray(scores, dtype=np.float64)
    if a.ndim != 1 or not len(a) or not np.isfinite(a).all():
        raise ValueError('Expected nonempty finite scores')
    if type(positive) is not int or not 0 <= positive < len(a):
        raise ValueError('Invalid positive index')
    value = a[positive]
    above = int(np.sum(a > value))
    tied = int(np.sum(a == value))
    out = {'reciprocal_rank': math.fsum(1.0 / r for r in range(above + 1, above + tied + 1)) / tied,
           'rank_best': above + 1, 'rank_worst': above + tied, 'tie_size': tied}
    out.update({f'recall_at_{k}': max(0, min(tied, k - above)) / tied for k in KS})
    return out


def random_metrics(n):
    if type(n) is not int or n < 1:
        raise ValueError('Candidate count must be positive')
    return {'reciprocal_rank': math.fsum(1.0 / r for r in range(1, n + 1)) / n,
            **{f'recall_at_{k}': min(k, n) / n for k in KS}}


def coordinate(well):
    import re
    if not re.fullmatch(r'[A-P](0[1-9]|1[0-9]|2[0-4])', well):
        raise ValueError('Expected canonical 384-well coordinate')
    return ord(well[0]) - ord('A'), int(well[1:]) - 1


def evaluate(gallery, queries, gallery_vectors, query_vectors):
    """Input records: broad_sample, jcp_id, well_position; unique exact IDs."""
    if len(gallery) != len(gallery_vectors) or len(queries) != len(query_vectors):
        raise ValueError('Record and vector lengths disagree')
    for records in (gallery, queries):
        for key in ('broad_sample', 'well_position'):
            if len({r[key] for r in records}) != len(records):
                raise ValueError('Duplicate eligible identity or well')
    scores = np.clip(query_vectors @ gallery_vectors.T, -1.0, 1.0)
    if not np.isfinite(scores).all():
        raise ValueError('Nonfinite similarity')
    results = []
    for qi, query in enumerate(queries):
        indices = [i for i, g in enumerate(gallery) if g['well_position'] != query['well_position']]
        positives = [local for local, i in enumerate(indices)
                     if gallery[i]['broad_sample'] == query['broad_sample']
                     and gallery[i]['jcp_id'] == query['jcp_id']]
        row = dict(query, candidate_count=len(indices), positive_count=len(positives))
        if len(positives) > 1:
            raise ValueError('More than one exact positive')
        if not positives:
            row['status'] = 'no_positive_after_prespecified_mask'
        else:
            row['status'] = 'evaluable'
            row['morphology'] = tie_metrics(scores[qi, indices], positives[0])
            qr, qc = coordinate(query['well_position'])
            position = []
            for i in indices:
                gr, gc = coordinate(gallery[i]['well_position'])
                position.append(-float((qr - gr) ** 2 + (qc - gc) ** 2))
            row['well_position_only'] = tie_metrics(position, positives[0])
            row['uniform_random_expectation'] = random_metrics(len(indices))
        results.append(row)
    eligible = [r for r in results if r['status'] == 'evaluable']
    metric_names = ['reciprocal_rank'] + [f'recall_at_{k}' for k in KS]
    aggregates = {}
    for method in ('morphology', 'well_position_only', 'uniform_random_expectation'):
        aggregates[method] = {name: math.fsum(r[method][name] for r in eligible) / len(eligible)
                              if eligible else None for name in metric_names}
    return {'query_count': len(queries), 'gallery_count': len(gallery),
            'evaluable_query_count': len(eligible), 'no_positive_query_count': len(queries) - len(eligible),
            'evaluable_fraction': len(eligible) / len(queries) if queries else None,
            'metrics_conditional_on_evaluability': aggregates,
            'weighting': 'equal weight per unique eligible exact design sample ID',
            'uncertainty': 'descriptive for one plate pair; no independent-plate CI or p-value'}, results
