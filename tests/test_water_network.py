import json,sqlite3,tempfile,unittest
from pathlib import Path
import numpy as np
from shapely.geometry import LineString
from hydraulics.reach_extraction import skeleton_paths,subdivide_path
from hydraulics.water_initialization import storage_depth
from scripts.build_water_network import gpkg


class WaterNetworkTests(unittest.TestCase):
    def test_branch_preserves_three_arms(self):
        s=np.zeros((7,7),bool);s[1:6,3]=True;s[3,3:6]=True
        paths=skeleton_paths(s)
        self.assertEqual(len(paths),3)
        ends=[p for path in paths for p in (path[0],path[-1])]
        self.assertEqual(ends.count((3,3)),3)
        self.assertEqual(sum(len(p)-1 for p in paths),6)

    def test_corner_has_no_diagonal_shortcut(self):
        s=np.zeros((3,3),bool);s[0,0:3]=True;s[0:3,2]=True
        paths=skeleton_paths(s)
        self.assertEqual(len(paths),1);self.assertEqual(len(paths[0]),5)

    def test_loop_is_kept(self):
        s=np.zeros((5,5),bool);s[1,1:4]=True;s[3,1:4]=True;s[1:4,1]=True;s[1:4,3]=True
        paths=skeleton_paths(s)
        self.assertEqual(len(paths),1);self.assertEqual(paths[0][0],paths[0][-1])
        self.assertEqual(len(paths[0])-1,8)

    def test_disconnected_channels_are_not_joined(self):
        s=np.zeros((5,8),bool);s[1,1:4]=True;s[3,4:7]=True
        self.assertEqual(len(skeleton_paths(s)),2)

    def test_subdivision_preserves_adjacency_and_endpoints(self):
        path=[(0,c) for c in range(12)];parts=list(subdivide_path(path,.5,2))
        self.assertEqual(parts[0][0],path[0]);self.assertEqual(parts[-1][-1],path[-1])
        for a,b in zip(parts,parts[1:]):self.assertEqual(a[-1],b[0])
        self.assertEqual(sum(len(p)-1 for p in parts),11)

    def test_storage_surface_is_level_not_constant_depth(self):
        z=np.array([[20.,20.4,20.6,np.nan]])
        h,level=storage_depth(z,np.ones_like(z,bool),25,.15)
        self.assertAlmostEqual(level,20.35)
        np.testing.assert_allclose(h,[[.35,0,0,0]])
        self.assertAlmostEqual((z+h)[0,0],level)

    def test_geopackage_has_geometry_not_json_blob(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.gpkg';gpkg(p,[('reaches','LINESTRING',[(LineString([(0,0),(1,0)]),{'id':'r1','source_ids':['a']})])])
            db=sqlite3.connect(p);blob=db.execute('SELECT geom FROM reaches').fetchone()[0]
            self.assertEqual(blob[:2],b'GP');self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT srs_id FROM gpkg_geometry_columns').fetchone()[0],32648)
            self.assertEqual(json.loads(db.execute('SELECT source_ids FROM reaches').fetchone()[0]),['a'])


class ReachFluxTests(unittest.TestCase):
    def test_staggered_uniform_flux_integrates_width_and_sign(self):
        import rasterio
        from rasterio.transform import from_origin
        from hydraulics.reach_flow import integrate_section,section_geometry
        from shapely.geometry import box
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'flux.tif'
            with rasterio.open(p,'w',driver='GTiff',width=40,height=40,count=3,dtype='float32',transform=from_origin(0,20,.5,.5),crs='EPSG:32648',nodata=-9999) as dst:
                dst.write(np.ones((40,40),np.float32)*.2,1);dst.write(np.ones((40,40),np.float32)*.4,2);dst.write(np.ones((40,40),np.float32)*.1,3)
            line=LineString([(5,10),(15,10)]);section,tangent,capped=section_geometry(line,box(0,8,20,12))
            self.assertFalse(capped)
            with rasterio.open(p) as src:
                a=integrate_section(src,section,tangent);b=integrate_section(src,section,-tangent)
            self.assertTrue(a['valid']);self.assertAlmostEqual(a['discharge_m3_s'],1.6,places=6)
            self.assertAlmostEqual(a['wetted_area_m2'],.8,places=6);self.assertAlmostEqual(b['discharge_m3_s'],-1.6,places=6)

    def test_section_clips_to_local_channel_not_other_parallel_channel(self):
        from hydraulics.reach_flow import section_geometry
        from shapely.geometry import box
        water=box(0,8,20,12).union(box(0,15,20,18))
        section,tangent,capped=section_geometry(LineString([(5,10),(15,10)]),water)
        self.assertAlmostEqual(section.length,4.);self.assertFalse(capped)

    def test_wide_section_search_cap_is_explicit(self):
        from hydraulics.reach_flow import section_geometry
        from shapely.geometry import box
        section,tangent,capped=section_geometry(LineString([(5,10),(15,10)]),box(-2000,-2000,2000,2000),half_length=100)
        self.assertTrue(capped)

class RasterConnectivityTests(unittest.TestCase):
    def test_diagonal_only_contact_does_not_create_face_connection(self):
        s=np.eye(3,dtype=bool)
        self.assertEqual(len(skeleton_paths(s,s)),0)
        water=s.copy();water[0,1]=True;water[1,2]=True
        self.assertEqual(len(skeleton_paths(s,water)),1)

class StaggeringTests(unittest.TestCase):
    def test_linear_face_field_sampled_at_face_not_cell_center(self):
        import rasterio
        from rasterio.transform import from_origin
        from hydraulics.reach_flow import integrate_section,section_geometry
        from shapely.geometry import box
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'linear.tif'
            with rasterio.open(p,'w',driver='GTiff',width=40,height=40,count=3,dtype='float32',transform=from_origin(0,20,.5,.5),crs='EPSG:32648',nodata=-9999) as dst:
                dst.write(np.ones((40,40),np.float32),1)
                dst.write(np.broadcast_to((np.arange(40,dtype=np.float32)+1)*.5,(40,40)),2)
                dst.write(np.zeros((40,40),np.float32),3)
            section,tangent,capped=section_geometry(LineString([(5,10),(15,10)]),box(0,8,20,12))
            with rasterio.open(p) as src:sample=integrate_section(src,section,tangent)
            self.assertAlmostEqual(sample['discharge_m3_s'],40.,places=8)

class MappedInitializationTests(unittest.TestCase):
    def test_channel_stage_does_not_wet_high_banks(self):
        import rasterio,shapefile
        from rasterio.transform import from_origin
        from hydraulics.water_initialization import initialize_mapped_water
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);tf=from_origin(0,10,.5,.5);z=np.ones((20,40),np.float32)*4;z[8:12,:]=0
            with shapefile.Writer(str(base/'angkor_center_features'),shapeType=5) as writer:
                writer.field('FID','C');writer.field('TYPE','N');writer.poly([[(0,0),(0,10),(20,10),(20,0),(0,0)]]);writer.record('canal',2)
            with shapefile.Writer(str(base/'angkor_center_lineartraces'),shapeType=3) as writer:writer.field('FID','C');writer.field('TYPE','N')
            stage=base/'stage.tif'
            with rasterio.open(stage,'w',driver='GTiff',height=20,width=40,count=1,dtype='float32',crs='EPSG:32648',transform=tf,nodata=-9999) as dst:dst.write(np.ones_like(z)*.2,1)
            c={'initial_stage_percentile':25,'initial_stage_offset_m':.15,'conduit_stage_file':str(stage)}
            h,report=initialize_mapped_water(z,tf,base,c)
            self.assertTrue(np.all(h[z==4]==0));np.testing.assert_allclose(h[z==0],.2)
            self.assertEqual(report['initial_wet_cells'],160)

if __name__=='__main__':unittest.main()
