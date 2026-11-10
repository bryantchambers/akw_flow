"""Hydraulic acceptance gates on synthetic known geometry, not calibration."""
import unittest
import numpy as np
from hydraulics.terrain import storage, stage_from_volume, face_geometry, simulate


def mesh(z, faces, profiles):
    return dict(terrain_samples_m=z,face_from=[p[0] for p in faces],face_to=[p[1] for p in faces],face_profiles_m=profiles,cell_area_m2=100.,spacing_m=10.)


class TerrainTests(unittest.TestCase):
    def config(self, **kw):
        return dict(duration_s=20,dt_max_s=.1,output_interval_s=5,manning_n=.05,**kw)

    def test_storage_inverse_and_dry(self):
        z=np.array([[0.,1.,2.,3.],[1.,1.,1.,1.]])
        for stage in (np.array([0.,1.]), np.array([.5,1.5]),np.array([4.,5.])):
            v=storage(stage,z,100)
            np.testing.assert_allclose(stage_from_volume(v,z,100),stage)

    def test_lake_at_rest_irregular_bed(self):
        m=mesh([[0.,1.],[.5,1.5]],[(0,1)],[[1.,1.2]])
        r=simulate(m,self.config(initial_stage_m=[2.,2.]))
        self.assertEqual(r['frames'][-1]['flows_m3_s'],[0.])
        self.assertAlmostEqual(r['budget']['residual_m3'],0)

    def test_separate_crests_and_widening(self):
        profiles=np.array([[1.,1.2,1.4,1.6],[2.,2.2,2.4,2.6]])
        _,w,_=face_geometry(np.array([1.3,1.3]),np.zeros(2),profiles,2.5)
        np.testing.assert_allclose(w,[5.,0.])
        _,w,_=face_geometry(np.array([2.3,2.3]),np.zeros(2),profiles,2.5)
        np.testing.assert_allclose(w,[10.,5.])

    def test_intact_bank_blocks_flow(self):
        m=mesh([[0.,0.],[0.,0.]],[(0,1)],[[2.,2.]])
        r=simulate(m,self.config(initial_stage_m=[1.,0.]))
        self.assertEqual(r['frames'][-1]['depth_m'],[1.,0.])

    def test_wetting_and_tracer_conservation(self):
        m=mesh([[0.,0.],[0.,0.]],[(0,1)],[[.2,.2]])
        r=simulate(m,self.config(initial_stage_m=[1.,0.],initial_tracer_concentration=[1.,0.]))
        self.assertGreater(r['frames'][-1]['depth_m'][1],0)
        self.assertGreater(r['frames'][-1]['tracer_concentration'][1],0)
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=8)
        self.assertAlmostEqual(r['tracer_budget']['residual'],0,places=8)
        self.assertTrue(all(min(f['depth_m'])>=0 for f in r['frames']))

    def test_reverse_flow(self):
        m=mesh([[0.,0.],[0.,0.]],[(0,1)],[[0.,0.]])
        r=simulate(m,self.config(initial_stage_m=[0.,1.]))
        self.assertLess(r['frames'][1]['flows_m3_s'][0],0)

    def test_multiple_outlets_rise_and_recession(self):
        m=mesh([[0.,0.]]*3,[(0,1),(0,2)],[[.5,.6],[1.1,1.2]])
        c=self.config(initial_stage_m=[.4,0.,0.],stage_boundaries=[{'cells':[0],'series':[[0,.4],[5,1.5],[10,1.5],[20,.1]],'tracer_concentration':1.}])
        r=simulate(m,c)
        self.assertEqual(r['frames'][0]['active_width_m'],[0.,0.])
        self.assertTrue(all(r['ever_active_faces']))
        self.assertTrue(any(f['flows_m3_s'][0]<0 for f in r['frames'][2:]))
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=7)
        self.assertAlmostEqual(r['tracer_budget']['residual'],0,places=7)

    def test_rain_infiltration_and_groundwater_budget(self):
        m=mesh([[0.,0.],[0.,0.]],[(0,1)],[[1.,1.]])
        r=simulate(m,self.config(initial_stage_m=[.1,.1],initial_tracer_concentration=1.,rainfall_mm_hr=10,infiltration_mm_hr=20,groundwater={'enabled':True,'conductance_m2_s_per_cell':.01,'head_m':0.}))
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=7)
        self.assertAlmostEqual(r['tracer_budget']['residual'],0,places=7)
        self.assertLess(r['budget']['groundwater_net_m3'],0)

    def test_invalid_boundary_rejected(self):
        m=mesh([[0.,0.],[0.,0.]],[(0,1)],[[0.,0.]])
        with self.assertRaises(ValueError):simulate(m,self.config(stage_boundaries=[{'cells':[0],'series':[[0,1],[2,1]]}]))

if __name__=='__main__':unittest.main()
