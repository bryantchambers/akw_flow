"""Metadata/numerical checks; not independent ground validation.
Run with the GIS environment: python -m unittest discover -s tests -v
"""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
import numpy as np
import pyproj
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('topsar',ROOT/'scripts/build_topsar_scenes.py')
topsar=importlib.util.module_from_spec(spec);spec.loader.exec_module(topsar)

class TopsarConversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=ROOT/'assets/data/context/topsar'
        with (cls.folder/'ts1260_c.demi2').open('rb') as f:cls.header=f.read(18640)
        cls.crs,cls.forward,cls.reverse=topsar.transforms(13.4925251,103.8435593,-160.1500854)

    def test_raw_integrity_and_header_layout(self):
        raw=self.folder/'ts1260_c.demi2';meta=json.loads((self.folder/'acquisition.json').read_text())
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),meta['sha256'])
        self.assertEqual(topsar.field(self.header,'BYTE OFFSET OF FIRST DATA RECORD ='),18640)
        self.assertEqual(raw.stat().st_size,18640+12136*2330*2)

    def test_header_corners_match_sch_not_assumed_utm(self):
        geod=pyproj.Geod(ellps='WGS84')
        for i,(r,c) in enumerate([(0,0),(0,2329),(12135,2329),(12135,0)],1):
            lon,lat,_=self.forward.transform(-30196.9+r*5,3986.8+c*5,0)
            x=topsar.field(self.header,f'LONGITUDE OF CORNER {i} =');y=topsar.field(self.header,f'LATITUDE OF CORNER {i} =')
            self.assertLess(geod.inv(lon,lat,x,y)[2],2)

    def test_sch_agrees_with_independent_ecef_formula(self):
        phi,lam,heading=np.radians([13.4925251,103.8435593,-160.1500854]);a=6378137.;e2=.0066943799901413165
        N=a/np.sqrt(1-e2*np.sin(phi)**2);M=a*(1-e2)/(1-e2*np.sin(phi)**2)**1.5
        R=N*M/(N*np.cos(heading)**2+M*np.sin(heading)**2)
        up=np.array([np.cos(phi)*np.cos(lam),np.cos(phi)*np.sin(lam),np.sin(phi)])
        east=np.array([-np.sin(lam),np.cos(lam),0]);north=np.array([-np.sin(phi)*np.cos(lam),-np.sin(phi)*np.sin(lam),np.cos(phi)])
        along=north*np.cos(heading)+east*np.sin(heading);cross=north*np.sin(heading)-east*np.cos(heading)
        peg=np.array([N*np.cos(phi)*np.cos(lam),N*np.cos(phi)*np.sin(lam),N*(1-e2)*np.sin(phi)])
        centre=peg-R*up;to_geo=pyproj.Transformer.from_crs(4978,4979,always_xy=True)
        for s,c,h in [(-30196.9,3986.8,0),(0,10000,25),(25000,15000,100)]:
            xyz=centre+(R+h)*(up*np.cos(c/R)*np.cos(s/R)+along*np.cos(c/R)*np.sin(s/R)+cross*np.sin(c/R))
            expected=to_geo.transform(*xyz);actual=self.forward.transform(s,c,h)
            np.testing.assert_allclose(actual[:2],expected[:2],rtol=0,atol=1e-9)
            self.assertLess(abs(actual[2]-expected[2]),1e-6)

    def test_native_detail_retains_gaps_and_has_no_inferred_flow(self):
        scene=json.loads((self.folder/'viewer_topsar_detail.json').read_text())
        self.assertEqual([scene['width'],scene['height']],[400,400])
        self.assertTrue(all(4.9<x<5.1 for x in scene['terrain']['display_pixel_metres_approx']))
        self.assertTrue(any(x is None for x in scene['elevation_m']))
        self.assertIsNone(scene['screening']);self.assertIsNone(scene['screening_area_km2'])
        self.assertEqual(scene['hotspots'],[])
        self.assertEqual(scene['terrain']['native_pixel_metres_approx'],[5,5])
        self.assertIn('ellipsoidal',scene['terrain']['vertical_reference'])
        self.assertGreater(scene['grid_bbox_wsen'][0],scene['bbox_wsen'][0])
        self.assertLess(scene['grid_bbox_wsen'][2],scene['bbox_wsen'][2])

if __name__=='__main__':unittest.main()
