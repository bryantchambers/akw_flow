import copy,json,unittest
from pathlib import Path
from hydraulics.model import simulate
class GroundwaterTests(unittest.TestCase):
 def settings(self):
  return copy.deepcopy(json.loads(Path('configs/humanum_flow.json').read_text())['groundwater'])
 def run_case(self,head):
  g=self.settings();g.update(enabled=True,column_area_m2=10,initial_head_relative_to_bed_m=head,bed_hydraulic_conductivity_m_s=.01)
  n={'nodes':[{'id':'a','bed_elevation_m':0,'storage_area_m2':10,'initial_depth_m':1}],'edges':[]}
  return simulate(n,{'duration_s':10,'dt_max_s':.01,'groundwater':g})
 def test_infiltration_and_total_conservation(self):
  r=self.run_case(0)
  self.assertLess(r['samples'][-1]['volumes_m3'][0],10)
  self.assertGreater(r['groundwater_budget']['surface_to_groundwater_net_m3'],0)
  self.assertAlmostEqual(r['groundwater_budget']['combined_residual_m3'],0,places=9)
 def test_exfiltration(self):
  r=self.run_case(2)
  self.assertGreater(r['samples'][-1]['volumes_m3'][0],10)
  self.assertLess(r['groundwater_budget']['surface_to_groundwater_net_m3'],0)
  self.assertAlmostEqual(r['budget']['residual_m3'],0,places=9)
 def test_equal_heads_stationary(self):
  r=self.run_case(1);self.assertAlmostEqual(r['samples'][-1]['volumes_m3'][0],10)
 def test_invalid_storage_parameters(self):
  from hydraulics.groundwater import Groundwater
  g=self.settings();g['specific_yield']=.9
  with self.assertRaises(ValueError):Groundwater([{'bed_elevation_m':0,'storage_area_m2':1}],[],g)
 def test_permeability_conversion(self):
  from hydraulics.groundwater import Groundwater
  g=self.settings();g['conductivity_mode']='intrinsic_permeability'
  model=Groundwater([{'bed_elevation_m':0,'storage_area_m2':1}],[],g)
  self.assertAlmostEqual(model.k[0],1e-13*1000*9.80665/.001)
