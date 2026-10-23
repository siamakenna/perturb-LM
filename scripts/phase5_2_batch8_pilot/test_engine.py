import itertools
import unittest
import numpy as np
from engine import fit_controls, transform, tie_metrics, evaluate


class EngineTests(unittest.TestCase):
    def test_mad_reference_and_zero_feature(self):
        c, s, k = fit_controls([[0, 7], [2, 7], [4, 7]])
        np.testing.assert_array_equal(c, [2, 7])
        np.testing.assert_allclose(s, [2 * 1.4826, 0])
        np.testing.assert_array_equal(k, [True, False])

    def test_target_values_do_not_change_fit(self):
        controls = np.array([[0., 0.], [1., 2.], [2., 4.]])
        c, s, k = fit_controls(controls)
        original = [v.copy() for v in (c, s, k)]
        transform([[100, -300]], c, s, k)
        for before, after in zip(original, (c, s, k)):
            np.testing.assert_array_equal(before, after)

    def test_zero_norm_and_invalid_matrix_fail(self):
        c, s, k = fit_controls([[0, 0], [1, 2], [2, 4]])
        with self.assertRaises(ValueError): transform([[1, 2]], c, s, k)
        with self.assertRaises(ValueError): transform([[float('nan'), 2]], c, s, k)
        with self.assertRaises(ValueError): fit_controls([[1, 1], [1, 1]])

    def test_tie_expectation_matches_exhaustive_oracle(self):
        # One higher score, three tied, one lower. Positive is any member of tie.
        got = tie_metrics([9, 5, 5, 5, 0], 2)
        ranks = [1 + perm.index('positive') + 1 for perm in itertools.permutations(['a','positive','b'])]
        self.assertAlmostEqual(got['reciprocal_rank'], sum(1/r for r in ranks)/len(ranks))
        self.assertEqual(got['rank_best'], 2)
        self.assertEqual(got['rank_worst'], 4)
        self.assertEqual(got['recall_at_1'], 0)
        self.assertEqual(got['recall_at_5'], 1)

    def test_ties_do_not_use_identifier_order(self):
        for pos in range(3):
            result = tie_metrics([1., 1., 1.], pos)
            self.assertAlmostEqual(result['recall_at_1'], 1/3)
            self.assertAlmostEqual(result['reciprocal_rank'], (1 + .5 + 1/3)/3)

    def test_all_gallery_candidates_retained_and_missing_positive_counted(self):
        gallery = [dict(broad_sample=x, jcp_id=x, well_position=w) for x,w in [('a','A01'),('b','A02'),('c','A03')]]
        queries = [dict(broad_sample=x, jcp_id=x, well_position=w) for x,w in [('a','B01'),('z','B02')]]
        summary, rows = evaluate(gallery, queries, np.array([[1.,0],[0,1],[-1,0]]), np.array([[1.,0],[0,1]]))
        self.assertEqual(summary['evaluable_query_count'], 1)
        self.assertEqual(summary['no_positive_query_count'], 1)
        self.assertEqual(rows[0]['candidate_count'], 3)
        self.assertEqual(rows[0]['morphology']['reciprocal_rank'], 1)
        self.assertAlmostEqual(rows[0]['uniform_random_expectation']['recall_at_1'], 1/3)

    def test_same_coordinate_mask_applied_before_metrics(self):
        gallery = [dict(broad_sample='a', jcp_id='a', well_position='A01')]
        summary, rows = evaluate(gallery, gallery, np.array([[1.,0]]), np.array([[1.,0]]))
        self.assertEqual(rows[0]['candidate_count'], 0)
        self.assertEqual(summary['evaluable_query_count'], 0)
        self.assertIsNone(summary['metrics_conditional_on_evaluability']['morphology']['reciprocal_rank'])

    def test_metadata_identity_disagreement_is_not_positive(self):
        gallery = [dict(broad_sample='a', jcp_id='J1', well_position='A01')]
        queries = [dict(broad_sample='a', jcp_id='J2', well_position='B01')]
        summary, _ = evaluate(gallery, queries, np.array([[1.,0]]), np.array([[1.,0]]))
        self.assertEqual(summary['evaluable_query_count'], 0)

    def test_gallery_order_invariance(self):
        gallery = [dict(broad_sample=x, jcp_id=x, well_position=w) for x,w in [('a','A01'),('b','A02')]]
        queries = [dict(broad_sample='a', jcp_id='a', well_position='B01')]
        v = np.array([[1.,0],[0,1]])
        first, _ = evaluate(gallery, queries, v, np.array([[1.,0]]))
        second, _ = evaluate(gallery[::-1], queries, v[::-1], np.array([[1.,0]]))
        self.assertEqual(first, second)


if __name__ == '__main__': unittest.main()
