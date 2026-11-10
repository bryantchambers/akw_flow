import unittest
import numpy as np
from hydraulics.terrain_review import disconnected_pools,aggregate_nested

class ReviewTests(unittest.TestCase):
    def test_subcell_bank_splits_pools(self):
        z=np.zeros((10,10));z[:,5]=2
        self.assertEqual(disconnected_pools(z,1)['pool_count'],2)
        self.assertEqual(disconnected_pools(z,3)['pool_count'],1)

    def test_diagonal_touch_not_a_connection(self):
        z=np.ones((4,4))*2;z[:2,:2]=0;z[2:,2:]=0
        self.assertEqual(disconnected_pools(z,1)['pool_count'],2)

    def test_tiny_pool_screened(self):
        z=np.ones((5,5))*2;z[0,0]=0
        self.assertEqual(disconnected_pools(z,1)['pool_count'],0)

    def test_volume_weighted_aggregation(self):
        c={'parameters':{'grid_spacing_m':10},'nodes':[{'id':'terrain:r0c0'}],
           'frames':[{'time_s':0,'depth_m':[1.],'tracer_concentration':[.5]}]}
        f={'parameters':{'grid_spacing_m':5},'nodes':[{'id':f'terrain:r{r}c{col}'} for r in (0,1) for col in (0,1)],
           'frames':[{'time_s':0,'depth_m':[0.,1.,2.,1.],'tracer_concentration':[0.,1.,.5,0.]}]}
        out=aggregate_nested(c,f)[0]
        self.assertEqual(out['fine_depth_m'],[1.]);self.assertEqual(out['fine_tracer_concentration'],[.5]);self.assertEqual(out['depth_difference_m'],[0.])
        f['nodes'].pop()
        with self.assertRaises(ValueError):aggregate_nested(c,f)

    def test_time_alignment_required(self):
        c={'parameters':{'grid_spacing_m':10},'nodes':[{'id':'terrain:r0c0'}],'frames':[{'time_s':0}]}
        f={'parameters':{'grid_spacing_m':10},'nodes':[{'id':'terrain:r0c0'}],'frames':[{'time_s':1}]}
        with self.assertRaises(ValueError):aggregate_nested(c,f)

if __name__=='__main__':unittest.main()
