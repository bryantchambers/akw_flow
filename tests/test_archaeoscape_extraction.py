import unittest
import numpy as np
from scripts.extract_archaeoscape_network import extract

class LocalExtractionTests(unittest.TestCase):
    def settings(self):
        return dict(pixel_size_m=.5,relief_radius_m=1,minimum_contributing_area_m2=1,
                    minimum_relative_depression_m=0,minimum_component_length_m=0)
    def valley(self):
        r,c=np.indices((32,32));return .1*(32-r)+.05*(c-16)**2
    def test_downhill_metric_geometry_and_anonymous_coordinates(self):
        net=extract(self.valley(),self.settings());self.assertGreater(len(net['edges']),0)
        nodes={n['id']:n for n in net['nodes']}
        for e in net['edges']:
            a,b=nodes[e['from']],nodes[e['to']]
            self.assertGreater(a['terrain_elevation_m_local'],b['terrain_elevation_m_local'])
            self.assertAlmostEqual(np.linalg.norm(np.array(a['local_xy_m'])-b['local_xy_m']),e['length_m'])
            self.assertNotIn('coordinates',a)
    def test_higher_area_threshold_only_removes_links(self):
        c=self.settings();a=extract(self.valley(),c);c['minimum_contributing_area_m2']=10
        b=extract(self.valley(),c)
        self.assertTrue({e['id'] for e in b['edges']} <= {e['id'] for e in a['edges']})
        self.assertLess(len(b['edges']),len(a['edges']))
    def test_nodata_and_exclusions_do_not_bridge(self):
        z=self.valley();z[:,16]=np.nan;c=self.settings();c['excluded_cells_rc']=[[10,10]]
        net=extract(z,c);nodes={n['id']:n for n in net['nodes']}
        for e in net['edges']:
            a,b=nodes[e['from']]['row_col'],nodes[e['to']]['row_col']
            self.assertTrue(a[1]<16 and b[1]<16 or a[1]>16 and b[1]>16)
            self.assertNotIn([10,10],[a,b])
    def test_constant_elevation_offset_preserves_graph(self):
        a=extract(self.valley(),self.settings());b=extract(self.valley()+100,self.settings())
        self.assertEqual([e['id'] for e in a['edges']],[e['id'] for e in b['edges']])
    def test_flats_create_no_invented_flow(self):
        self.assertEqual(extract(np.ones((32,32)),self.settings())['edges'],[])
    def test_smoothing_maintains_hole_exclusion(self):
        z=self.valley();z[16,16]=np.nan;c=self.settings();c['smoothing_sigma_m']=.5
        net=extract(z,c)
        for n in net['nodes']:
            r,col=n['row_col'];self.assertGreater(max(abs(r-16),abs(col-16)),4)
