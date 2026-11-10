import unittest
import numpy as np
from rasterio.transform import from_origin
from hydraulics.fixed_geometry import apply_fixed_edits,apply_initial_levels

class FixedGeometryTests(unittest.TestCase):
    def setUp(self):
        self.tf=from_origin(0,2,.5,.5)
        self.geometry={'type':'Polygon','coordinates':[[[0,1],[1,1],[1,2],[0,2],[0,1]]]}
    def test_fixed_edit_changes_only_native_polygon_and_keeps_nodata(self):
        z=np.ones((4,4),np.float32);z[0,0]=np.nan
        apply_fixed_edits(z,self.tf,[{'geometry_projected':self.geometry,'mode':'raise','elevation_m':2,'evidence':'test crest scenario'}])
        self.assertTrue(np.isnan(z[0,0]));self.assertEqual(z[1,1],2);self.assertEqual(z[3,3],1)
    def test_initial_levels_respect_mapped_water(self):
        z=np.ones((4,4),np.float32);h=np.zeros((4,4));water=np.zeros((4,4),np.uint8);water[0,0]=1
        apply_initial_levels(h,z,water,self.tf,[{'geometry_projected':self.geometry,'stage_m':2,'evidence':'hypothetical water level'}])
        self.assertEqual(h[0,0],1);self.assertEqual(h[1,1],0)
    def test_evidence_and_mode_required(self):
        z=np.ones((4,4),np.float32)
        with self.assertRaises(ValueError):apply_fixed_edits(z,self.tf,[{'geometry_projected':self.geometry,'mode':'raise','elevation_m':2}])
        with self.assertRaises(ValueError):apply_fixed_edits(z,self.tf,[{'geometry_projected':self.geometry,'mode':'erode','elevation_m':2,'evidence':'test'}])

if __name__=='__main__':unittest.main()
