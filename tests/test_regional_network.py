import unittest
from shapely.geometry import box
from scripts.build_regional_network import feature_contacts,partition,shared_interfaces,components
class RegionalTests(unittest.TestCase):
 def test_contact_and_gap_are_distinct(self):
  f=[{'id':'a','geom':box(0,0,10,10)},{'id':'b','geom':box(10,0,20,10)},{'id':'c','geom':box(25,0,35,10)}]
  e=feature_contacts(f,5)
  self.assertEqual(len(e),2)
  self.assertEqual(e[0]['status'],'geometric_contact_unverified')
  self.assertEqual(e[1]['status'],'proposed_gap_requires_review')
  self.assertEqual(components(['a','b','c'],[e[0]]),[2,1])
 def test_partition_does_not_double_count_overlaps(self):
  f=[{'id':'canal','kind':'Canal','geom':box(0,0,20,10)},{'id':'pond','kind':'Pond','geom':box(10,0,30,10)}]
  c,_=partition(f,10,.01)
  self.assertAlmostEqual(sum(x['geom'].area for x in c),300)
  for i,a in enumerate(c):
   for b in c[i+1:]:self.assertAlmostEqual(a['geom'].intersection(b['geom']).area,0)
  self.assertEqual(len(shared_interfaces(c)),2)
 def test_point_contacts_are_not_hydraulic_interfaces(self):
  c=[{'id':'a','geom':box(0,0,1,1)},{'id':'b','geom':box(1,1,2,2)}]
  self.assertEqual(shared_interfaces(c),[])
 def test_disconnected_parts_do_not_become_one_cell(self):
  f=[{'id':'p','kind':'Pond','geom':box(0,0,1,1).union(box(3,0,4,1))}]
  c,_=partition(f,10,.1);self.assertEqual(len(c),2);self.assertEqual(shared_interfaces(c),[])
 def test_small_slivers_are_reported(self):
  c,qc=partition([{'id':'p','kind':'Pond','geom':box(0,0,1,1)}],10,2)
  self.assertFalse(c);self.assertAlmostEqual(qc[0]['area_m2'],1)
