import copy
import math
import unittest
from transport.core import simulate

class TransportTests(unittest.TestCase):
    def base(self):
        return dict(cells=[dict(id='a',volume_m3=10,bed_area_m2=1),dict(id='b',volume_m3=10,bed_area_m2=1)], initial_concentration=[1,0],duration_s=10,dt_max_s=.01)
    def test_closed_diffusion_analytical(self):
        c=self.base(); c['connections']=[dict(**{'from':'a','to':'b'},flow_m3_s=0,dispersion_m2_s=1,area_m2=1,distance_m=1)]
        r=simulate(c)
        self.assertAlmostEqual(r['concentration'][0],.5+.5*math.exp(-2),delta=.0002)
        self.assertAlmostEqual(r['mass_budget']['residual'],0,places=10)
    def test_cstr_flushing(self):
        c=self.base(); c['cells']=c['cells'][:1]; c['initial_concentration']=1
        c['boundaries']=[dict(cell='a',flow_m3_s=1,concentration=0),dict(cell='a',flow_m3_s=-1)]
        r=simulate(c)
        self.assertAlmostEqual(r['concentration'][0],math.exp(-1),delta=.0003)
        self.assertAlmostEqual(r['mass_budget']['residual'],0,places=10)
    def test_reverse_flow_and_ledger(self):
        c=self.base(); c['initial_concentration']=[0,1]
        c['connections']=[dict(**{'from':'a','to':'b'},flow_m3_s=-1)]
        c['boundaries']=[dict(cell='b',flow_m3_s=1,concentration=1),dict(cell='a',flow_m3_s=-1)]
        r=simulate(c)
        self.assertGreater(r['concentration'][0],.6)
        self.assertAlmostEqual(r['mass_budget']['residual'],0,places=10)
    def test_unbalanced_fixed_rejected(self):
        c=self.base(); c['connections']=[dict(**{'from':'a','to':'b'},flow_m3_s=1)]
        with self.assertRaisesRegex(ValueError,'water balance'): simulate(c)
    def test_dynamic_dilution(self):
        c=self.base(); c['boundaries']=[dict(cell='a',flow_m3_s=1,concentration=0)]; c['dynamic_volumes']=True
        r=simulate(c)
        self.assertAlmostEqual(r['volumes_m3'][0],20,places=9)
        self.assertAlmostEqual(r['concentration'][0],.5,places=9)
        self.assertAlmostEqual(r['mass_budget']['residual'],0,places=10)
    def test_biological_death(self):
        c=self.base(); c['model']='biological'; c['parameters']=dict(dark_enabled=True,dark_water_s=.1,dark_bed_s=.1)
        r=simulate(c)
        self.assertAlmostEqual(r['concentration'][0],math.exp(-1),delta=.0003)
        self.assertAlmostEqual(r['mass_budget']['residual'],0,places=10)
    def test_no_mutation(self):
        c=self.base(); before=copy.deepcopy(c); simulate(c); self.assertEqual(c,before)

if __name__=='__main__': unittest.main()
