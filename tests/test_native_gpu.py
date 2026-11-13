"""Hardware tests are skipped on CPU-only hosts; Slurm benchmark requires them."""
import unittest
from unittest.mock import patch
import numpy as np
from hydraulics import native_grid as native


class BackendDispatchTests(unittest.TestCase):
    def test_explicit_gpu_never_silently_falls_back(self):
        with patch.object(native,'gpu_available',return_value=False):
            with self.assertRaises(RuntimeError):native.simulate(np.zeros((1,1)),np.zeros((1,1)),{'backend':'gpu'})

    def test_auto_selects_cpu_without_cuda(self):
        with patch.object(native,'gpu_available',return_value=False):
            r=native.simulate(np.zeros((1,1)),np.zeros((1,1)),{'duration_s':.01,'backend':'auto','threads':1})
        self.assertEqual(r['execution']['backend'],'cpu')

    def test_unknown_backend_rejected(self):
        with self.assertRaises(ValueError):native.simulate(np.zeros((1,1)),np.zeros((1,1)),{'backend':'other'})


@unittest.skipUnless(native.gpu_available(),'Requires an allocated CUDA GPU and numba-cuda')
class GpuParityTests(unittest.TestCase):
    def compare(self,z,h,c=None,**options):
        cfg=dict(spacing_m=.5,duration_s=.12,dt_max_s=.004,threads=2,manning_n=.05,progress_interval_wall_s=1000);cfg.update(options)
        a=native.simulate(z,h,{**cfg,'backend':'cpu'},c)
        b=native.simulate(z,h,{**cfg,'backend':'gpu'},c)
        self.assertEqual(a['steps'],b['steps'])
        for key in ('depth','mass_per_area','qx_per_width','qy_per_width','momentum_depth'):
            np.testing.assert_allclose(b[key],a[key],atol=1e-9,rtol=1e-8,err_msg=key)
        for key in ('budget','tracer_budget'):
            self.assertLess(abs(b[key]['residual' if key=='tracer_budget' else 'residual_m3']),1e-9*max(1.,b[key]['initial_mass' if key=='tracer_budget' else 'initial_volume_m3']))
        self.assertGreaterEqual(float(b['depth'].min()),0)
        self.assertGreaterEqual(float(b['mass_per_area'].min()),0)
        return a,b

    def test_lake_at_rest(self):
        z=np.array([[0.,.2],[.3,.1]],np.float32);h=1.-z.astype(float)
        _,b=self.compare(z,h,np.ones_like(h));np.testing.assert_allclose(b['depth'],h,atol=1e-12)

    def test_wetting_tracer_and_nodata(self):
        z=np.array([[0.,0.,np.nan,0.]],np.float32);h=np.array([[.1,0,0,0.]])
        _,b=self.compare(z,h,np.array([[1.,0,0,0.]]));self.assertGreater(b['depth'][0,1],0);self.assertEqual(b['depth'][0,3],0)

    def test_multiple_outlets_and_below_crest_blocking(self):
        z=np.array([[0.,1.,0.,2.,0.]],np.float32)
        h=np.zeros_like(z,dtype=float);h[0,2]=1.5
        _,b=self.compare(z,h);self.assertEqual(b['depth'][0,3],0)
        h[0,2]=2.5;_,b=self.compare(z,h);self.assertGreater(b['depth'][0,1],0);self.assertGreater(b['depth'][0,3],0)

    def test_rain_infiltration_and_partial_concentration(self):
        rng=np.random.default_rng(17);z=np.zeros((17,33),np.float32);h=np.ones(z.shape)*.1;c=rng.random(z.shape)
        self.compare(z,h,c,rainfall_mm_hr=30,infiltration_mm_hr=10)

    def test_reverse_flux_and_non_multiple_block_shape(self):
        rng=np.random.default_rng(23);z=rng.random((19,37),dtype=np.float32)*.01;h=np.zeros(z.shape);h[:,20:]=.2
        c=np.zeros(z.shape);c[:,20:]=.7
        _,b=self.compare(z,h,c);self.assertLess(float(b['qx_per_width'].min()),0)
        active=b['depth']>1e-6
        self.assertLessEqual(float((b['mass_per_area'][active]/b['depth'][active]).max()),.700000001)

    def test_sustained_rainfall_volume_and_dilution(self):
        z=np.zeros((129,257),np.float32);z[:,128]=.2
        h=np.zeros(z.shape);h[:,:128]=.05;c=np.zeros(z.shape);c[:,:128]=1.
        _,b=self.compare(z,h,c,rainfall_mm_hr=60,duration_s=60,dt_max_s=.1)
        expected=60/3.6e6*60*z.size*.25
        self.assertAlmostEqual(b['budget']['rainfall_m3'],expected,places=8)
        wet=b['depth']>=1e-6
        self.assertLessEqual(float((b['mass_per_area'][wet]/b['depth'][wet]).max()),1.00000001)

    def test_single_cell_and_single_column(self):
        self.compare(np.zeros((1,1),np.float32),np.ones((1,1))*.1)
        h=np.zeros((9,1));h[0]=.1;self.compare(np.zeros_like(h,np.float32),h)

    def test_transpose_and_bidirectional_flow(self):
        z=np.zeros((9,11),np.float32);h=np.zeros_like(z,dtype=float);h[4,5]=.2
        _,b=self.compare(z,h)
        self.assertGreater(float(b['qx_per_width'].max()),0);self.assertLess(float(b['qx_per_width'].min()),0)
        self.assertGreater(float(b['qy_per_width'].max()),0);self.assertLess(float(b['qy_per_width'].min()),0)


class PreferredRegionalCliTests(unittest.TestCase):
    def test_default_gpu_producer_requires_slurm_before_creating_output(self):
        import os,subprocess,sys,tempfile
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        env=os.environ.copy();env.pop('SLURM_JOB_ID',None)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'not-created'
            result=subprocess.run([sys.executable,str(root/'scripts/build_regional_native.py'),'--output',str(out)],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertIn('submit_regional_gpu.py',result.stderr)
            self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
