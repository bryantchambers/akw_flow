#!/usr/bin/env python3
"""Audit legacy regional graph/cell artifacts; private outputs stay in .runtime."""
import json,collections,math
from pathlib import Path
import shapefile,numpy as np
from shapely import make_valid,STRtree
from shapely.geometry import shape,Point,LineString
from pyproj import Transformer
root=Path(__file__).resolve().parents[1];base=root/'assets/private';graph=json.loads((base/'regional_network/feature_graph.json').read_text());cells=json.loads((base/'regional_network/cell_network.json').read_text());manifest=json.loads((base/'regional_network/manifest.json').read_text())
features={};multipart=[]
for name in ['angkor_center_features','angkor_center_lineartraces']:
 for r in shapefile.Reader(str(base/'humanum_danish_edna'/name)).iterShapeRecords():
  typ=int(r.record['TYPE'])
  if (name.endswith('features') and typ not in (1,2,4)) or (name.endswith('lineartraces') and typ!=2):continue
  g=make_valid(shape(r.shape.__geo_interface__));ident=name+':'+str(r.record['FID']);features[ident]=g
  if g.geom_type=='MultiPolygon':multipart.append({'id':ident,'parts':len(g.geoms),'type':typ})
xy=Transformer.from_crs(4326,32648,always_xy=True);nodes={n['id']:n for n in graph['nodes']};lengths=[];active=[]
for e in graph['edges']:
 if not e['scenario_enabled']:continue
 pts=[xy.transform(*nodes[e['from']]['coordinates']),*e['connection_xy_m'],xy.transform(*nodes[e['to']]['coordinates'])];drawn=LineString(pts).length
 rec={'id':e['id'],'gap_m':e['gap_m'],'drawn_anchor_link_m':drawn};active.append(rec);lengths.append(drawn)
for rec in active:
 e=next(e for e in graph['edges'] if e['id']==rec['id']);intersection=features[e['from']].intersection(features[e['to']]);rec['contact_type']=intersection.geom_type;rec['shared_boundary_m']=features[e['from']].boundary.intersection(features[e['to']].boundary).length;rec['overlap_area_m2']=intersection.area
large=sorted(cells['nodes'],key=lambda n:n['storage_area_m2'],reverse=True)[:5];degree=collections.Counter()
for e in cells['edges']:degree[e['from']]+=1;degree[e['to']]+=1
longcell=sorted(cells['edges'],key=lambda e:e['length_m'],reverse=True)[:10]
report={'features':len(graph['nodes']),'feature_links':len(graph['edges']),'active_feature_links':len(active),'active_contacts_by_type':dict(collections.Counter(r['contact_type'] for r in active)),
 'active_drawn_anchor_links_over_1km':sum(x>1000 for x in lengths),'longest_active_drawn_anchor_link_m':max(lengths),'largest_drawn_links':sorted(active,key=lambda r:r['drawn_anchor_link_m'],reverse=True)[:8],
 'multipart_water_features':len(multipart),'multipart_examples':sorted(multipart,key=lambda r:r['parts'],reverse=True)[:8],
 'cells':len(cells['nodes']),'cell_interfaces':len(cells['edges']),'components':len(manifest['cell_components']),'largest_components':manifest['cell_components'][:5],
 'largest_cells':[{'id':n['id'],'kind':n['kind'],'area_m2':n['storage_area_m2'],'degree':degree[n['id']]} for n in large],
 'longest_solver_links':[{'id':e['id'],'length_m':e['length_m'],'width_m':e['width_m']} for e in longcell],
 'source_counts':manifest['source_counts'],'parameters':manifest['parameters'],'budget':manifest['budget']}
(root/'.runtime/regional-guide').mkdir(parents=True,exist_ok=True)
(root/'.runtime/regional-guide/audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
