import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
from hydraulics import regional_view as view
from hydraulics.regional_faces import faces
from hydraulics.face_index import strongest,reduce_records
from scripts.build_regional_face_index import build

class FaceSelectionTests(unittest.TestCase):
    def test_signed_peak_and_identity_preserved(self):
        q=np.zeros((4,4),np.float32);q[1,2]=-.04;q[3,3]=.02
        v,r,c=strongest(q,2)
        self.assertAlmostEqual(float(v[0,1]),-.04);self.assertEqual((r[0,1],c[0,1]),(1,2))
        combined=reduce_records(np.stack((v,r,c)),2)
        self.assertEqual((combined[1,0,0],combined[2,0,0]),(1,2));self.assertLess(combined[0,0,0],0)
    def test_no_data_does_not_win_and_partial_bins(self):
        q=np.full((3,3),np.nan,np.float32);q[2,2]=.1
        v,r,c=strongest(q,2)
        self.assertEqual(r[0,0],-1);self.assertEqual((r[1,1],c[1,1]),(2,2))

class NativeFaceViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.override=patch.object(view,'OUT',self.root);self.override.start()
        self.tf=from_origin(376650,1483680,.5,.5)
        self.profile=dict(driver='GTiff',width=128,height=128,count=6,dtype='float32',crs='EPSG:32648',transform=self.tf,nodata=-9999)
        a=np.zeros((6,128,128),np.float32);a[0]=.1;a[1,50,50]=-.02;a[2,60,60]=.04
        with rasterio.open(self.root/'final.tif','w',**self.profile) as d:d.write(a)
        self.profile['count']=1
        with rasterio.open(self.root/'initial.tif','w',**self.profile) as d:d.write(a[0],1)
        (self.root/'manifest.json').write_text(json.dumps({'status':'complete'}))
    def tearDown(self):self.override.stop();self.temp.cleanup()
    def bounds(self,r0,c0,r1,c1):
        x0,y1=self.tf @ (c0,r0);x1,y0=self.tf @ (c1,r1)
        p=[view.TOGEO.transform(x,y) for x in (x0,x1) for y in (y0,y1)]
        return [min(x[0] for x in p),min(x[1] for x in p),max(x[0] for x in p),max(x[1] for x in p)]
    def test_native_geometry_and_signed_discharge(self):
        d=faces(self.bounds(45,45,65,65),minimum_q=1e-5)
        self.assertEqual(d['mode'],'native');self.assertTrue(d['grid_lines'])
        e=next(f for f in d['faces'] if f['id']=='r50c50:east')
        self.assertAlmostEqual(e['discharge_m3_s'],-.01,places=6)
        x0,y0=view.TOUTM.transform(*e['face_coordinates'][0]);x1,y1=view.TOUTM.transform(*e['face_coordinates'][1])
        self.assertAlmostEqual(x0,x1,places=5);self.assertAlmostEqual(abs(y1-y0),.5,places=5)
    def test_overview_finds_narrow_flow_and_preserves_exact_location(self):
        build(self.root)
        d=faces(self.bounds(0,0,128,128),minimum_q=1e-5)
        self.assertEqual(d['mode'],'representative')
        self.assertTrue(any(f['id']=='r50c50:east' for f in d['faces']))
        self.assertTrue(any(f['id']=='r60c60:south' for f in d['faces']))
        # A flow remains signed, not averaged with zero-flow neighbours.
        self.assertAlmostEqual(next(f['discharge_m3_s'] for f in d['faces'] if f['id']=='r50c50:east'),-.01,places=6)
    def test_initial_state_does_not_invent_flow(self):
        d=faces(self.bounds(45,45,65,65),'initial')
        self.assertEqual(d['faces'],[]);self.assertTrue(d['grid_lines'])
    def test_idle_faces_have_no_invented_discharge(self):
        d=faces(self.bounds(5,5,10,10),include_idle=True)
        self.assertTrue(d['faces']);self.assertTrue(all(f['discharge_m3_s']==0 for f in d['faces']))
    def test_stale_index_is_rejected(self):
        build(self.root);p=self.root/'face_index.json';meta=json.loads(p.read_text());meta['source_state']['size']+=1;p.write_text(json.dumps(meta))
        with self.assertRaises(ValueError):faces(self.bounds(0,0,128,128))
    def test_invalid_settings(self):
        with self.assertRaises(ValueError):faces([0,0,1,1],minimum_q=-1)
        with self.assertRaises(ValueError):faces([float('nan'),0,1,1])

if __name__=='__main__':unittest.main()
