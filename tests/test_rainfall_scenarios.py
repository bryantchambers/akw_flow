import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np,rasterio
from hydraulics.rainfall_scenarios import validate,reach_comparison,raster_comparison
from scripts.run_rainfall_scenarios import prepare

class RainfallScenarioTests(unittest.TestCase):
    def config(self):return {'duration_s':600,'rainfall_intensities_mm_hr':[0,5,60],'infiltration_mm_hr':0,'minimum_face_discharge_m3_s':1e-5,'minimum_face_depth_m':.01,'minimum_reach_discharge_m3_s':1e-5,'comparison_depth_thresholds_m':[.01,.1],'base_configuration':'base.json'}

    def test_control_and_duration_are_required(self):
        self.assertEqual(validate(self.config()),(600.,[0.,5.,60.]))
        for rates in ([5,60],[0,60,5],[0,5,5],[0,float('nan')]):
            c=self.config();c['rainfall_intensities_mm_hr']=rates
            with self.assertRaises(ValueError):validate(c)

    def test_prepare_freezes_identical_parameters_except_rain_and_label(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'base.json').write_text(json.dumps({'manning_n':.05,'backend':'gpu','terrain_modifications':[]}));config=root/'config.json';config.write_text(json.dumps(self.config()))
            with patch('scripts.run_rainfall_scenarios.ROOT',root),patch('scripts.run_rainfall_scenarios.BASE',root/'private'):
                directory=prepare(config,'rain_test')
                a=json.loads((directory/'r0.json').read_text());b=json.loads((directory/'r60.json').read_text())
                for p in (a,b):
                    for key in ('rainfall_mm_hr','rainfall_case_id','scenario_label'):p.pop(key)
                self.assertEqual(a,b)
                suite=json.loads((directory/'suite.json').read_text());self.assertEqual(suite['cases'][-1]['total_rainfall_mm'],10.)
                with self.assertRaises(ValueError):prepare(config,'rain_test')

    def test_flow_reversal_and_new_directionality_are_not_new_geometry(self):
        def feature(key,q,d):return {'properties':{'id':key,'discharge_m3_s':q,'flow_direction':d}}
        control=[feature('a',1,1),feature('b',0,0),feature('c',None,0)]
        selected=[feature('a',-2,-1),feature('b',.5,1),feature('c',None,0)]
        result=reach_comparison(selected,control)
        self.assertEqual(result['directional_class_changes']['reversed_direction'],1);self.assertEqual(result['directional_class_changes']['newly_directional'],1)
        self.assertEqual(selected[0]['properties']['delta_discharge_m3_s'],-3)
        self.assertEqual(selected[0]['properties']['id'],'a')

    def test_raster_difference_uses_face_flux_and_predictor_depth(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[Path(d)/'control',Path(d)/'rain']
            for index,path in enumerate(paths):
                path.mkdir()
                with rasterio.open(path/'final.tif','w',driver='GTiff',width=2,height=2,count=6,dtype='float32',transform=rasterio.transform.from_origin(0,1,.5,.5),crs='EPSG:32648',nodata=-9999) as dst:
                    a=np.zeros((6,2,2),np.float32);a[0]=.1+index*.1;a[1,0,0]=.2 if index==0 else -.2;a[4,0,0]=1 if index==0 else -1
                    if index:a[2,1,0]=.3;a[5,1,0]=1
                    dst.write(a)
            r=raster_comparison(paths[1],paths[0],self.config())
            self.assertEqual(r['reversed_faces'],1);self.assertEqual(r['newly_flowing_faces'],1)
            self.assertAlmostEqual(r['mean_depth_difference_m'],.1,places=6)
            self.assertEqual(r['area_at_or_above_depth_m_m2']['0.1'],1.)

if __name__=='__main__':unittest.main()
