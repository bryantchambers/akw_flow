import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString
import hydraulics.channel_review as review

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Path(self.temp.name)/'review.json'
  self.graph={'nodes':[{'id':'a'},{'id':'b'}],'edges':[{'id':'ab','from':'a','to':'b'}]}
  self.patches=[patch.object(review,'STORE',self.store),patch.object(review,'graph',return_value=self.graph),patch.object(review,'CACHE',{'hash':'test-hash'})]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.temp.cleanup()
 def request(self,**kw):
  return {'category':'links','id':'ab','expected_revision':0,'graph_sha256':'test-hash','decision':'accepted','evidence':'Synthetic test evidence','notes':'Test rationale',**kw}
 def test_saved_review_and_audit_survive_reload(self):
  result=review.save(self.request());self.assertEqual(result['revision'],1);self.assertEqual(review.state()['links']['ab']['decision'],'accepted');self.assertEqual(len(result['history']),1)
  result=review.save(self.request(expected_revision=1,decision='rejected'));self.assertEqual(result['history'][1]['before']['decision'],'accepted')
 def test_stale_revision_and_network_rejected(self):
  review.save(self.request())
  with self.assertRaises(ValueError):review.save(self.request())
  with self.assertRaises(ValueError):review.save(self.request(expected_revision=1,graph_sha256='other'))
 def test_unknown_id_and_acceptance_without_evidence(self):
  for change in ({'id':'missing'},{'evidence':''},{'notes':''},{'decision':'guess'}):
   with self.assertRaises(ValueError):review.save(self.request(**change))
 def test_reach_ranges_validate_and_do_not_accept_connections(self):
  result=review.save(self.request(category='features',id='a',incision_m=.5,incision_range_m=[.2,.8],manning_n=.035,manning_range=[.02,.06]));self.assertFalse(result['links']);self.assertEqual(result['features']['a']['incision_m'],.5)
  with self.assertRaises(ValueError):review.save(self.request(category='features',id='b',expected_revision=1,incision_m=2,incision_range_m=[0,1]))

class TerrainSamplingTests(unittest.TestCase):
 def test_planar_profile_metric_stations_and_nodata(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'terrain.tif';r,c=np.indices((10,10));z=(2*(c+.5)+3*(9.5-r)).astype('float32');z[4,4]=-9999
   with rasterio.open(path,'w',driver='GTiff',height=10,width=10,count=1,dtype='float32',transform=from_origin(0,10,1,1),crs='EPSG:32648',nodata=-9999) as dst:dst.write(z,1)
   with rasterio.open(path) as src:profile=review.sampled_line(src,LineString([(.5,5.5),(8.5,5.5)]),spacing=1)
   self.assertEqual(profile['station_m'],list(np.arange(9,dtype=float)));self.assertIsNone(profile['elevation_m'][4])
   for i,z in enumerate(profile['elevation_m']):
    if z is not None:self.assertAlmostEqual(z,2*(i+.5)+3*5.5)
   self.assertAlmostEqual(profile['valid_fraction'],8/9)

class ReviewHTTPTests(unittest.TestCase):
 def test_api_validation_and_origin_guard(self):
  import threading,urllib.request,urllib.error
  from http.server import ThreadingHTTPServer
  from server import Handler
  fake={'nodes':[{'id':'a'},{'id':'b'}],'edges':[{'id':'ab','from':'a','to':'b'}]}
  with tempfile.TemporaryDirectory() as folder,patch.object(review,'STORE',Path(folder)/'reviews.json'),patch.object(review,'graph',return_value=fake),patch.object(review,'CACHE',{'hash':'test-hash'}):
   server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
   request={'category':'links','id':'ab','expected_revision':0,'graph_sha256':'test-hash','decision':'accepted','notes':'Synthetic test only','evidence':'Unit test'}
   try:
    bad=urllib.request.Request(base+'/api/channel-review/save',data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Origin':'http://other.invalid'})
    with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(bad)
    self.assertEqual(err.exception.code,403);self.assertFalse(review.STORE.exists())
    req=urllib.request.Request(base+'/api/channel-review/save',data=json.dumps(request).encode(),headers={'Content-Type':'application/json'})
    result=json.load(urllib.request.urlopen(req));self.assertEqual(result['revision'],1)
    with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
    self.assertEqual(err.exception.code,400)
   finally:server.shutdown();server.server_close();thread.join()

class CrossSectionTests(unittest.TestCase):
 def test_cross_sections_are_normal_to_custom_guide_and_source_unchanged(self):
  from shapely.geometry import box
  from pyproj import Transformer
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);p=root/'assets/private/humanum_danish_edna';p.mkdir(parents=True);path=p/'dtm_angkor_center.tif'
   r,c=np.indices((100,100));z=(c+.5).astype('float32')
   with rasterio.open(path,'w',driver='GTiff',height=100,width=100,count=1,dtype='float32',transform=from_origin(500000,1400100,1,1),crs='EPSG:32648',nodata=-9999) as dst:dst.write(z,1)
   before=path.read_bytes();tg=Transformer.from_crs(32648,4326,always_xy=True)
   guide=[list(tg.transform(x,1400050)) for x in (500025,500075)]
   with patch.object(review,'ROOT',root),patch.object(review,'geometry',return_value=box(500020,1400020,500080,1400080)):
    result=review.profile({'feature_id':'a','guide_coordinates':guide,'cross_section_half_width_m':20})
   self.assertEqual(len(result['cross_sections']),3);self.assertAlmostEqual(result['length_m'],50,places=5)
   for cross in result['cross_sections']:
    a,b=np.array(cross['xy_m'][0]),np.array(cross['xy_m'][-1]);self.assertAlmostEqual(a[0],b[0],places=5);self.assertGreater(a[1],b[1]);self.assertAlmostEqual(cross['station_m'][0],-20);self.assertAlmostEqual(cross['station_m'][-1],20)
   self.assertEqual(path.read_bytes(),before)

class ReviewModelApplicationTests(unittest.TestCase):
 def test_saved_decisions_apply_to_contacts_and_proposals(self):
  contact={'id':'a','gap_m':0};gap={'id':'b','gap_m':10}
  self.assertTrue(review.connection_enabled(contact,set(),set(),{}));self.assertFalse(review.connection_enabled(gap,set(),set(),{}))
  self.assertFalse(review.connection_enabled(contact,set(),set(),{'a':{'decision':'unresolved'}}))
  self.assertFalse(review.connection_enabled(contact,set(),set(),{'a':{'decision':'rejected'}}))
  self.assertTrue(review.connection_enabled(gap,set(),set(),{'b':{'decision':'accepted'}}))
 def test_reach_parameters_apply_with_explicit_fallback(self):
  records={'a':{'incision_m':.8,'manning_n':.03}}
  self.assertAlmostEqual(review.feature_incision(records,'a',.5),.8);self.assertAlmostEqual(review.feature_incision(records,'b',.5),.5)
  self.assertAlmostEqual(review.interface_manning(records,'a','a',.05),.03)
  self.assertAlmostEqual(review.interface_manning(records,'a','b',.05),.05)
  self.assertIsNone(review.interface_manning(records,'b','c',.05))
