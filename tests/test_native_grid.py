import unittest
import numpy as np
from hydraulics.native_grid import simulate
from hydraulics.terrain import simulate as reference

class NativeGridTests(unittest.TestCase):
    def config(self,**kw):
        return dict(spacing_m=.5,duration_s=.5,dt_max_s=.01,threads=2,progress_interval_wall_s=1000,**kw)

    def test_lake_at_rest(self):
        z=np.array([[0.,.2],[.3,.1]],np.float32);h=1.-z.astype(float)
        r=simulate(z,h,self.config(),initial_concentration=np.ones_like(h))
        np.testing.assert_allclose(r['depth'],h,atol=1e-12)
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=10)
        self.assertAlmostEqual(r['tracer_budget']['residual'],0,places=10)

    def test_ridge_blocks_below_crest(self):
        z=np.array([[0.,2.,0.]],np.float32);h=np.array([[1.,0.,0.]])
        r=simulate(z,h,self.config())
        np.testing.assert_allclose(r['depth'],h)

    def test_wetting_and_no_data_barrier(self):
        z=np.array([[0.,0.,np.nan,0.]],np.float32);h=np.array([[.1,0.,0.,0.]])
        r=simulate(z,h,self.config(),initial_concentration=np.array([[1.,0.,0.,0.]]))
        self.assertGreater(r['depth'][0,1],0)
        self.assertEqual(r['depth'][0,3],0)
        self.assertGreater(r['mass_per_area'][0,1],0)
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=10)
        self.assertAlmostEqual(r['tracer_budget']['residual'],0,places=10)

    def test_rainfall_and_infiltration(self):
        z=np.zeros((3,3),np.float32);h=np.ones((3,3))*.1
        r=simulate(z,h,self.config(rainfall_mm_hr=30,infiltration_mm_hr=10),initial_concentration=np.ones_like(h))
        np.testing.assert_allclose(r['depth'],.1+20/3.6e6*.5)
        self.assertAlmostEqual(r['budget']['residual_m3'],0,places=10)
        self.assertAlmostEqual(r['tracer_budget']['residual'],0,places=10)

    def test_matches_existing_face_solver_on_native_chain(self):
        z=np.zeros((1,3),np.float32);h=np.array([[.1,.05,0.]])
        cfg=self.config();cfg.update(duration_s=.1,dt_max_s=.0005);native=simulate(z,h,cfg,initial_concentration=np.array([[1.,0.,0.]]))
        mesh=dict(terrain_samples_m=[[0.],[0.],[0.]],face_from=[0,1],face_to=[1,2],face_profiles_m=[[0.],[0.]],cell_area_m2=.25,spacing_m=.5)
        ref=reference(mesh,dict(duration_s=.1,dt_max_s=.0005,output_interval_s=.1,manning_n=.05,initial_stage_m=h.ravel().tolist(),initial_tracer_concentration=[1.,0.,0.]))
        np.testing.assert_allclose(native['depth'].ravel(),ref['frames'][-1]['depth_m'],atol=1e-6)
        self.assertAlmostEqual(native['budget']['residual_m3'],0,places=10)

    def test_full_and_transposed_domain_conserve(self):
        z=np.zeros((4,5),np.float32);h=np.zeros_like(z,dtype=float);h[1,1]=.2
        a=simulate(z,h,self.config());b=simulate(z.T.copy(),h.T.copy(),self.config())
        np.testing.assert_allclose(a['depth'],b['depth'].T,atol=1e-10)
        self.assertGreater(a['depth'][1,2],0)
        self.assertGreater(a['depth'][2,1],0)

    def test_uniform_slope_matches_analytic_local_inertial_solution(self):
        import math
        slope=.0001;h=.1;n=.05
        z=(20-slope*np.arange(2000)[None,:]*.5).astype('float32')
        r=simulate(z,np.ones_like(z,dtype=float)*h,dict(spacing_m=.5,duration_s=100,dt_max_s=.01,manning_n=n,threads=1))
        qeq=h**(5/3)*math.sqrt(slope)/n;tau=qeq/(9.80665*h*slope)
        expected=qeq*math.tanh(100/tau)
        self.assertAlmostEqual(float(r['qx_per_width'][0,950:1050].mean())/expected,1.,places=4)

    def test_unsupported_groundwater_rejected(self):
        with self.assertRaises(ValueError):simulate(np.zeros((2,2)),np.ones((2,2)),self.config(groundwater={'enabled':True}))

if __name__=='__main__':unittest.main()
