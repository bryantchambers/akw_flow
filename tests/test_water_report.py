import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np,rasterio
from pypdf import PdfReader
from scripts import build_water_diagnosis as report


class WaterReportTests(unittest.TestCase):
    def test_completed_case_produces_readable_review_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'assets/private/water_system';model=out/'hydraulics';model.mkdir(parents=True)
            values={'network_manifest':{'reaches':1,'nodes':2,'waterbodies':1,'ports':1,'components':1},'coupling':{}}
            for name,value in values.items():(out/(name+'.json')).write_text(json.dumps(value))
            (model/'manifest.json').write_text(json.dumps({'valid_area_km2':.4096,'valid_cells':1638400,'parameters':{'duration_s':1},'budget':{'residual_m3':0}}))
            (model/'verification.json').write_text(json.dumps({'status':'passed','faces_with_froude_over_one_and_face_depth_at_least_1cm':1,'maximum_exported_face_velocity_m_s':.1}))
            (model/'view_comparison.json').write_text(json.dumps({'center_utm_m':[376650,1483680],'extent_m':640}))
            for directory,names in [('regional_native',['initial']),('water_system/hydraulics',['initial','final'])]:
                p=root/'assets/private'/directory;p.mkdir(exist_ok=True,parents=True)
                for name in names:
                    with rasterio.open(p/(name+'.tif'),'w',driver='GTiff',width=1280,height=1280,count=1,dtype='float32',transform=rasterio.transform.from_origin(376330,1484000,.5,.5),crs='EPSG:32648',nodata=-9999,compress='deflate') as dst:dst.write(np.ones((1280,1280),np.float32)*.1,1)
            with patch.object(report,'ROOT',root),patch.object(report,'OUT',out),patch.object(report,'FOLDER',root/'knowledge/Fixed-terrain model'):pdf=report.build()
            pages=PdfReader(pdf).pages;self.assertEqual(len(pages),5)
            text=' '.join(p.extract_text() for p in pages)
            self.assertIn('not the original pilot extended',text);self.assertIn('does not reproduce the pilot hydrograph',text)

if __name__=='__main__':unittest.main()
