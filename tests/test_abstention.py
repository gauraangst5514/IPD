import unittest
from research.abstention import upper_tail_threshold, binomial_upper

class AbstentionTests(unittest.TestCase):
    def test_insufficient_groups_abstains_instead_of_using_interpolated_quantile(self):
        self.assertEqual(upper_tail_threshold(list(range(10)), .05), float('inf'))
        self.assertEqual(upper_tail_threshold(list(range(19)), .05), 18.)

    def test_invalid_calibration_is_rejected(self):
        for scores in ([], [float('nan')], [float('inf')]):
            with self.assertRaises(ValueError): upper_tail_threshold(scores, .05)
        for alpha in (0, 1, -1):
            with self.assertRaises(ValueError): upper_tail_threshold([.5], alpha)

    def test_no_observed_errors_does_not_imply_proven_low_risk(self):
        self.assertGreater(binomial_upper(0, 10), .25)
        self.assertEqual(binomial_upper(10, 10), 1.)
