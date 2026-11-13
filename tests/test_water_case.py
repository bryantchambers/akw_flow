import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from hydraulics import water_case,regional_view

class WaterCaseTests(unittest.TestCase):
    def test_only_verified_coupled_case_activates_and_stale_case_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);gpu=base/'hydraulics_gpu';gpu.mkdir()
            m={'status':'complete','execution':{'backend':'gpu'}}
            (gpu/'manifest.json').write_text(json.dumps(m));(gpu/'verification.json').write_text(json.dumps({'status':'passed'}))
            with patch.object(water_case,'BASE',base):
                with self.assertRaises(FileNotFoundError):water_case.activate(gpu)
                (base/'acceptance.json').write_text(json.dumps({'stage':'complete','model_directory':'hydraulics_gpu'}))
                (base/'coupling.json').write_text(json.dumps({'model_directory':'hydraulics_gpu'}))
                water_case.activate(gpu);self.assertEqual(water_case.active_directory(),gpu)
                (gpu/'manifest.json').write_text(json.dumps({'status':'prepared'}))
                self.assertEqual(water_case.active_directory(),base/'hydraulics')

    def test_pointer_cannot_escape_private_case_directory(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);(base/'active_case.json').write_text(json.dumps({'directory':'../outside'}))
            with patch.object(water_case,'BASE',base):
                with self.assertRaises(ValueError):water_case.active_directory()

    def test_request_scope_keeps_raster_directory_consistent(self):
        with patch.object(regional_view,'OUT',Path('/default')):
            token=regional_view.CASE_DIRECTORY.set(Path('/chosen'))
            try:self.assertEqual(regional_view.raster_path('height','initial'),Path('/chosen/terrain.tif'))
            finally:regional_view.CASE_DIRECTORY.reset(token)
            self.assertEqual(regional_view.raster_path('height','initial'),Path('/default/terrain.tif'))

if __name__=='__main__':unittest.main()
