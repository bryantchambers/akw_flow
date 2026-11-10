import json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
from hydraulics import regional_view as view

class RegionalViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.override=patch.object(view,'OUT',self.base);self.override.start();view._tile.cache_clear()
        self.tf=from_origin(376650,1483680,.5,.5)
        profile=dict(driver='GTiff',width=8,height=8,count=1,dtype='float32',crs='EPSG:32648',transform=self.tf,nodata=-9999)
        with rasterio.open(self.base/'terrain.tif','w',**profile) as d:d.write(np.ones((8,8),np.float32)*20,1)
        with rasterio.open(self.base/'initial.tif','w',**profile) as d:d.write(np.ones((8,8),np.float32)*.1,1)
        profile['count']=6
        with rasterio.open(self.base/'final.tif','w',**profile) as d:
            for i,v in enumerate((.2,.02,0.,.5,.1,0.),1):d.write(np.ones((8,8),np.float32)*v,i)
        (self.base/'manifest.json').write_text(json.dumps({'status':'complete','parameters':{'initial_unit_tracer_concentration':1}}))
    def tearDown(self):view._tile.cache_clear();self.override.stop();self.temp.cleanup()
    def test_point_reads_actual_native_cell(self):
        lon,lat=view.TOGEO.transform(376650.75,1483679.25)
        p=view.point(lon,lat,'final');self.assertEqual((p['row'],p['col']),(1,1))
        self.assertEqual(p['solver_spacing_m'],.5);self.assertAlmostEqual(p['water_depth_m'],.2,places=6)
        self.assertAlmostEqual(p['east_face_discharge_m3_s'],.01,places=6)
    def test_point_outside_and_bad_snapshot_rejected(self):
        with self.assertRaises(ValueError):view.point(0,0,'initial')
        with self.assertRaises(ValueError):view.point(103,13,'../../source')
    def test_windowed_tile_is_png(self):
        lon,lat=view.TOGEO.transform(376652,1483678);z=20;n=2**z
        x=int((lon+180)/360*n);y=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
        data=view.tile('depth','final',z,x,y);self.assertTrue(data.startswith(b'\x89PNG'))
        with self.assertRaises(ValueError):view.tile('depth','final',23,0,0)
    def test_hillshade_tile_is_png(self):
        lon,lat=view.TOGEO.transform(376652,1483678);z=20;n=2**z
        x=int((lon+180)/360*n);y=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
        self.assertTrue(view.tile('hillshade','initial',z,x,y).startswith(b'\x89PNG'))

    def test_stale_final_is_blocked_during_rebuild(self):
        (self.base/'manifest.json').write_text(json.dumps({'status':'prepared'}))
        with self.assertRaises(FileNotFoundError):view.raster_path('depth','final')

    def test_vector_uses_face_velocity_band(self):
        west,south=view.TOGEO.transform(376650,1483676);east,north=view.TOGEO.transform(376654,1483680)
        v=view.vectors([west,south,east,north],'final')
        self.assertTrue(v);self.assertAlmostEqual(v[0]['east_m_s'],.1,places=6)
        self.assertEqual(view.vectors([west,south,east,north],'initial'),[])
    def test_no_path_injection(self):
        with self.assertRaises(ValueError):view.raster_path('../../terrain','final')
        with self.assertRaises(ValueError):view.raster_path('depth','../source')

if __name__=='__main__':unittest.main()
