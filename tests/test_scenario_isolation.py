import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from hydraulics import water_network_view as view
from hydraulics.water_case import case_directory

class ScenarioIsolationTests(unittest.TestCase):
    def test_network_layers_and_downloads_follow_requested_case(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'hydraulics_gpu_rain_test_r0';b=root/'hydraulics_gpu_rain_test_r60'
            for model,q in ((a,1),(b,3)):
                network=model/'network';network.mkdir(parents=True)
                (model/'manifest.json').write_text(json.dumps({'status':'complete'}));(model/'final.tif').write_bytes(b'test')
                state={p.name:{'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (model/'manifest.json',model/'final.tif')}
                (network/'coupling.json').write_text(json.dumps({'status':'complete','model_directory':model.name,'model_source_state':state}))
                (network/'reaches.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'LineString','coordinates':[[103,13],[103.1,13.1]]},'properties':{'id':'same-geometry','discharge_m3_s':q}}]}))
                (network/'water_network.gpkg').write_bytes(b'test-gpkg-'+str(q).encode())
            with patch.object(view,'OUT',root),patch.object(view,'active_directory',return_value=a),patch.object(view,'case_directory',side_effect=lambda name=None:a if not name or name==a.name else b):
                first=view.layer('reaches',case=a.name);second=view.layer('reaches',case=b.name)
                self.assertEqual(first['features'][0]['properties']['discharge_m3_s'],1);self.assertEqual(second['features'][0]['properties']['discharge_m3_s'],3)
                self.assertEqual(view.download('water_network.gpkg',b.name)[0],b/'network/water_network.gpkg')
                self.assertTrue(view.coupling_current(json.loads((b/'network/coupling.json').read_text()),b))

    def test_unverified_case_is_not_selectable(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);case=base/'hydraulics_gpu_rain_test_r60';case.mkdir()
            with patch('hydraulics.water_case.BASE',base),patch('hydraulics.water_case.active_directory',return_value=base/'hydraulics_gpu'):
                with self.assertRaises(FileNotFoundError):case_directory(case.name)
                with self.assertRaises(ValueError):case_directory('../outside')

if __name__=='__main__':unittest.main()
