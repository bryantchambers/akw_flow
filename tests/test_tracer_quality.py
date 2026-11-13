import unittest
import numpy as np
from scripts.verify_regional_native import tracer_tile_quality

class TracerQualityTests(unittest.TestCase):
    def test_report_dry_roundoff_without_dropping_mass(self):
        q=tracer_tile_quality(np.array([1.2e-8,.1]),np.array([1.000071,1.]),1.,1e-6)
        self.assertEqual(q['dry_excursion_cells'],1);self.assertEqual(q['wet_max'],1.)
        self.assertGreater(q['dry_excess_mass'],0);self.assertLess(q['dry_excess_mass'],1e-12)

    def test_wet_bound_violation_still_fails(self):
        with self.assertRaises(ValueError):tracer_tile_quality(np.array([.1]),np.array([1.000071]),1.,1e-6)

    def test_extreme_dry_value_has_detectable_mass_not_exempt(self):
        q=tracer_tile_quality(np.array([1e-8]),np.array([1e12]),1.,1e-6)
        self.assertGreater(q['dry_excess_mass'],1000)

if __name__=='__main__':unittest.main()
