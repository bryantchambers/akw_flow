import tempfile,unittest
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from hydraulics.regional_pyramids import build_native_hillshade

class NativeHillshadeTests(unittest.TestCase):
    def test_native_spacing_and_no_tile_seams_on_plane(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'terrain_source_state.json').write_text('{"test":true}')
            rows,cols=np.indices((256,512));z=(20+.02*rows+.01*cols).astype('float32')
            profile=dict(driver='GTiff',height=256,width=512,count=1,dtype='float32',crs='EPSG:32648',transform=from_origin(376650,1483680,.5,.5),nodata=-9999,tiled=True,blockxsize=128,blockysize=128)
            with rasterio.open(root/'terrain.tif','w',**profile) as dst:dst.write(z,1)
            build_native_hillshade(root)
            with rasterio.open(root/'hillshade.tif') as src:
                self.assertEqual(src.res,(.5,.5));self.assertEqual(src.shape,z.shape)
                shade=src.read(1)[10:-10,10:-10]
                self.assertLessEqual(int(shade.max())-int(shade.min()),1)
                self.assertTrue(src.overviews(1))

if __name__=='__main__':unittest.main()
