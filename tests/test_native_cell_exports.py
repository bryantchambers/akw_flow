import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np,rasterio
from rasterio.transform import from_origin
from hydraulics import regional_view as view


class CellExportTests(unittest.TestCase):
    def test_native_cell_values_and_topological_face_signs(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);tf=from_origin(376000,1484000,.5,.5);profile=dict(driver='GTiff',width=2,height=2,dtype='float32',transform=tf,crs='EPSG:32648',nodata=-9999)
            for name,count in [('terrain',1),('initial',1),('final',6)]:
                with rasterio.open(out/(name+'.tif'),'w',count=count,**profile) as src:
                    a=np.zeros((count,2,2),np.float32)
                    if name=='terrain':a[:]=20
                    else:a[0]=.1
                    if name=='final':a[1]=.4;a[2]=-.2
                    src.write(a)
            (out/'manifest.json').write_text(json.dumps({'status':'complete'}))
            west,south=view.TOGEO.transform(376000,1483999);east,north=view.TOGEO.transform(376001,1484000)
            with patch.object(view,'OUT',out):data=view.cells([west,south,east,north],'final')
            self.assertEqual(len(data['features']),4)
            f=data['features'][0];p=f['properties'];self.assertEqual(p['area_m2'],.25)
            self.assertAlmostEqual(p['stage_m'],20.1,places=6);self.assertAlmostEqual(p['east_face_discharge_m3_s'],.2,places=6)
            self.assertAlmostEqual(p['south_face_discharge_m3_s'],-.1,places=6)
            ring=f['geometry']['coordinates'][0];self.assertEqual(ring[0],ring[-1])
            x,y=view.TOUTM.transform(*ring[0]);xx,yy=view.TOUTM.transform(*ring[2]);self.assertAlmostEqual(abs((xx-x)*(yy-y)),.25,places=7)

if __name__=='__main__':unittest.main()
