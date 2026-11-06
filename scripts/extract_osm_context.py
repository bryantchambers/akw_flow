#!/usr/bin/env python3
"""Extract modern water ways from a dated Geofabrik OSM snapshot; no archaeological interpretation."""
import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import osmium
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/data/context'
BBOX=[103.6,13.2,104.2,13.8]
URL='https://download.geofabrik.de/asia/cambodia-261104.osm.pbf'

class Water(osmium.SimpleHandler):
    def __init__(self):
        super().__init__();self.features=[];self.elements=[]
    def way(self,way):
        tags={t.k:t.v for t in way.tags}
        if not ('waterway' in tags or tags.get('natural')=='water' or tags.get('landuse')=='reservoir'):return
        coords=[[n.lon,n.lat] for n in way.nodes if n.location.valid()]
        if len(coords)<2:return
        w,s,e,n=BBOX
        if not any(w<=lon<=e and s<=lat<=n for lon,lat in coords):return
        polygon=len(coords)>=4 and coords[0]==coords[-1] and (tags.get('natural')=='water' or tags.get('landuse')=='reservoir')
        props=dict(tags,osm_type='way',osm_id=way.id,interpretation='Modern OSM feature; historical age and hydraulic connectivity unverified')
        self.features.append({'type':'Feature','id':'way/'+str(way.id),'properties':props,
          'geometry':{'type':'Polygon' if polygon else 'LineString','coordinates':[coords] if polygon else coords}})
        self.elements.append({'type':'way','id':way.id,'tags':tags,'geometry':[{'lon':p[0],'lat':p[1]} for p in coords]})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);pbf=OUT/'cambodia-261104.osm.pbf'
    if not pbf.exists():
        if not args.download:raise RuntimeError('OSM PBF not found; use --download')
        with urllib.request.urlopen(URL,timeout=120) as r:pbf.write_bytes(r.read())
    md5path=OUT/'cambodia-261104.osm.pbf.md5'
    if not md5path.exists():
        with urllib.request.urlopen(URL+'.md5',timeout=30) as r:md5path.write_bytes(r.read())
    assert hashlib.md5(pbf.read_bytes()).hexdigest()==md5path.read_text().split()[0], 'Source MD5 mismatch'
    with osmium.io.Reader(str(pbf)) as reader:timestamp=reader.header().get('osmosis_replication_timestamp')
    handler=Water();handler.apply_file(str(pbf),locations=True)
    assert handler.features,'No features extracted'
    raw=OUT/'osm_water_raw.json';raw.write_text(json.dumps({'generator':'Geofabrik PBF -> pyosmium; ways only','osm3s':{'timestamp_osm_base':timestamp},'elements':handler.elements})+'\n')
    geo=OUT/'osm_water_context.geojson';geo.write_text(json.dumps({'type':'FeatureCollection','name':'Angkor modern water context','description':'WGS84 lon/lat. Modern OSM ways intersecting provisional rectangle; not clipped; relations not assembled.','features':handler.features},ensure_ascii=False)+'\n')
    provenance=OUT/'provenance.json';doc=json.loads(provenance.read_text()) if provenance.exists() else {'working_bbox_wsen':BBOX,'records':[]}
    doc['records']=[r for r in doc['records'] if r.get('dataset')!='openstreetmap']
    doc['records'].append({'dataset':'openstreetmap','kind':'modern_water_features','path':str(pbf.relative_to(ROOT/'assets')),
      'source_url':URL,'retrieved_utc':datetime.fromtimestamp(pbf.stat().st_mtime,timezone.utc).isoformat(),
      'sha256':hashlib.sha256(pbf.read_bytes()).hexdigest(),'bytes':pbf.stat().st_size,
      'osm_base_timestamp':timestamp,'query_bbox_wsen':BBOX,'feature_count':len(handler.features),
      'derived_path':str(geo.relative_to(ROOT/'assets')),'derived_sha256':hashlib.sha256(geo.read_bytes()).hexdigest(),
      'license':'ODbL 1.0; © OpenStreetMap contributors','attribution':'https://www.openstreetmap.org/copyright',
      'processing':'scripts/extract_osm_context.py; ways only, retaining complete geometries with at least one vertex in the rectangle.'})
    provenance.write_text(json.dumps(doc,indent=2)+'\n')
    w,s,e,n=BBOX
    (OUT/'provisional_extent.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'status':'Provisional search rectangle, not a watershed'},'geometry':{'type':'Polygon','coordinates':[[[w,s],[e,s],[e,n],[w,n],[w,s]]]}}]})+'\n')
    print('Extracted',len(handler.features),'modern OSM water features; snapshot',timestamp,flush=True)
if __name__=='__main__':main()
