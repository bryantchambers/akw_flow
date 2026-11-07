import unittest
import numpy as np
from hydraulics.model import discharge,simulate
from scripts.build_channel_network import extract

class HydraulicTests(unittest.TestCase):
    def network(self):
        return {'nodes':[{'id':'a','bed_elevation_m':0.,'storage_area_m2':100.,'initial_depth_m':1.,'coordinates':[103.86,13.41]},{'id':'b','bed_elevation_m':0.,'storage_area_m2':100.,'initial_depth_m':.5,'coordinates':[103.861,13.41]}],'edges':[{'id':'ab','from':'a','to':'b','width_m':2.,'length_m':100.}]}
    def test_scenario_roughness_overrides_edge_default(self):
        n=self.network();n['edges'][0]['manning_n']=.03
        cfg={'duration_s':.01,'roughness':{'manning_n':.06}}
        r=simulate(n,cfg)
        self.assertAlmostEqual(r['samples'][0]['flows_m3_s'][0],discharge(1,2,.005,.06)['flow_m3_s'])
        cfg['edge_overrides']={'ab':{'manning_n':.09}}
        r=simulate(n,cfg)
        self.assertAlmostEqual(r['samples'][0]['flows_m3_s'][0],discharge(1,2,.005,.09)['flow_m3_s'])

    def test_manning_known(self):
        d=discharge(1.,2.,.001,.03)
        self.assertAlmostEqual(d['flow_m3_s'],2*(.5**(2/3))*(.001**.5)/.03)
        self.assertAlmostEqual(discharge(1,2,-.001,.03)['flow_m3_s'],-d['flow_m3_s'])
        self.assertAlmostEqual(discharge(1,2,.001,.06)['flow_m3_s'],d['flow_m3_s']/2)
    def test_closed_conservation_and_interval_flux(self):
        r=simulate(self.network(),{'duration_s':10,'dt_max_s':.01,'output_interval_s':2})
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=9)
        self.assertLess(r['samples'][-1]['volumes_m3'][0],100)
        for a,b in zip(r['samples'],r['samples'][1:]):
            q=b['preceding_interval_mean_flows_m3_s'][0]; dt=b['time_s']-a['time_s']
            self.assertAlmostEqual(b['volumes_m3'][0],a['volumes_m3'][0]-q*dt,places=9)
    def test_external_water_accounting(self):
        n=self.network();n['edges']=[]
        r=simulate(n,{'duration_s':10,'external_flows_m3_s':[1,-1]})
        np.testing.assert_allclose(r['samples'][-1]['volumes_m3'],[110,40],atol=1e-8)
    def test_laminar_requires_wide_section(self):
        with self.assertRaises(ValueError):discharge(1,2,.0001,.03,closure='laminar_wide')
        d=discharge(.001,2,1e-5,.03,closure='laminar_wide')
        self.assertAlmostEqual(d['velocity_m_s'],9.80665*.001**2*1e-5/(3e-6))
    def test_no_data_not_connected(self):
        s={'width':3,'height':3,'grid_bbox_wsen':[103.,13.,103.001,13.001],'elevation_m':[9,None,1,8,None,0,7,None,-1]}
        net,_,_=extract(s,threshold_m2=1)
        for edge in net['edges']:
            a=int(edge['from'][1:])%3;b=int(edge['to'][1:])%3
            self.assertEqual(a,b)
    def test_reject_invalid_geometry(self):
        n=self.network();n['nodes'][0]['storage_area_m2']=0
        with self.assertRaises(ValueError):simulate(n,{})
if __name__=='__main__':unittest.main()
