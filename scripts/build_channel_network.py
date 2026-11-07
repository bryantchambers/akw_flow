#!/usr/bin/env python3
"""Extract strict-downhill D8 terrain candidates, then run an explicit scenario.
Input viewer-scene JSON uses grid cell-centre bbox and null NoData. Substituting
registered LiDAR-derived scene JSON keeps this extraction interface unchanged.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.model import simulate,output_geojson
ROOT=Path(__file__).resolve().parents[1]


def extract(scene, bbox=None, threshold_m2=2500., stride=1):
    z=np.array(scene['elevation_m'],float).reshape(scene['height'],scene['width'])[::stride,::stride]
    w,s,e,n=scene['grid_bbox_wsen']; xs=np.linspace(w,e,scene['width'])[::stride];ys=np.linspace(n,s,scene['height'])[::stride]
    dx=abs(xs[1]-xs[0])*111320*math.cos(math.radians((s+n)/2));dy=abs(ys[1]-ys[0])*111320
    valid=np.isfinite(z)
    if bbox:
        bw,bs,be,bn=bbox;valid &= (xs[None,:]>=bw)&(xs[None,:]<=be)&(ys[:,None]>=bs)&(ys[:,None]<=bn)
    h,width=z.shape;target=np.full(z.size,-1,int);zflat=z.ravel();v=valid.ravel()
    # No filling, breaching, or routing across gaps. Ties terminate at flats.
    for idx in np.flatnonzero(v):
        r,c=divmod(int(idx),width);best=0.
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                rr,cc=r+dr,c+dc
                if not (dr or dc) or not (0<=rr<h and 0<=cc<width) or not valid[rr,cc]: continue
                slope=(z[r,c]-z[rr,cc])/math.hypot(dc*dx,dr*dy)
                if slope>best: best=slope;target[idx]=rr*width+cc
    acc=np.where(v,dx*dy,0.)
    for i in np.argsort(np.where(v,-zflat,np.inf)):
        if target[i]>=0:acc[target[i]]+=acc[i]
    selected=[int(i) for i in np.flatnonzero((acc>=threshold_m2)&(target>=0))]
    # Keep each sampled cell edge; this avoids inferring channels across sinks/gaps.
    used=sorted(set(selected)|{int(target[i]) for i in selected}); ids={i:f'n{i}' for i in used}
    nodes=[]
    for i in used:
        r,c=divmod(i,width)
        nodes.append(dict(id=ids[i],coordinates=[float(xs[c]),float(ys[r])],bed_elevation_m=float(zflat[i]),storage_area_m2=dx*dy,contributing_area_m2=float(acc[i])))
    edges=[];features=[]
    for i in selected:
        j=int(target[i]);r,c=divmod(i,width);rr,cc=divmod(j,width);eid=f'e{i}'
        edges.append(dict(id=eid,**{'from':ids[i],'to':ids[j]},length_m=math.hypot((c-cc)*dx,(r-rr)*dy),width_m=2.,geometry_status='hypothetical 2 m width; terrain-derived bed proxy'))
        features.append(dict(type='Feature',geometry=dict(type='LineString',coordinates=[[float(xs[c]),float(ys[r])],[float(xs[cc]),float(ys[rr])]]),properties=dict(id=eid,value=float(acc[i]),status='unverified terrain drainage candidate')))
    network=dict(nodes=nodes,edges=edges,assumptions=['Strict-downhill D8 candidates are not archaeological channel identifications.','Radar elevations are unvalidated surface proxies, not measured channel beds.','2 m width and 0.1 m initial depth are illustrative; not inferred bathymetry.','Closed extraction domain; sinks retain water and no reservoir connectivity is inferred.'])
    geo=dict(type='FeatureCollection',model=dict(name='TOPSAR drainage candidates',scenario='Unconditioned strict-downhill D8',metric='terrain contributing area',unit='m2'),features=features)
    return network,geo,dict(valid_cells=int(valid.sum()),candidate_edges=len(edges),cell_area_m2=dx*dy,threshold_m2=threshold_m2,stride=stride)


def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,default=ROOT/'assets/data/context/topsar/viewer_topsar_detail.json');p.add_argument('--boundary',type=Path,default=ROOT/'assets/data/study_area/config.json');p.add_argument('--threshold-m2',type=float,default=2500);p.add_argument('--stride',type=int,default=1);p.add_argument('--output',type=Path,default=ROOT/'assets/data/hydraulics');a=p.parse_args()
    if a.stride<1 or a.threshold_m2<=0:raise ValueError('positive stride/threshold required')
    scene=json.loads(a.scene.read_text());boundary=json.loads(a.boundary.read_text()) if a.boundary.exists() else {}
    bbox=boundary.get('extraction_bbox_wsen',boundary.get('bbox_wsen',scene['bbox_wsen']))
    net,geo,qc=extract(scene,bbox,a.threshold_m2,a.stride)
    config=dict(duration_s=30.,dt_max_s=.05,output_interval_s=5.,initial_depth_m=.1,roughness=dict(manning_n=.035,viscosity_m2_s=1e-6,closure='manning',transition_re=500),edge_overrides={},external_flows_m3_s=[0.]*len(net['nodes']),status='Illustrative closed drainage relaxation; no observed forcing')
    result=simulate(net,config)
    a.output.mkdir(parents=True,exist_ok=True)
    payloads={'network.json':net,'candidate_network.geojson':geo,'scenario.json':config,'simulation.json':result,'flow_output.geojson':output_geojson(net,result),'extraction_qc.json':dict(qc,source=str(a.scene.relative_to(ROOT)) if a.scene.is_relative_to(ROOT) else str(a.scene),source_sha256=hashlib.sha256(a.scene.read_bytes()).hexdigest(),requested_bbox=bbox,available_bbox=scene['bbox_wsen'],coverage_note='Only finite source grid cells are used; unobserved West Baray and interconnecting channels are excluded.')}
    for name,data in payloads.items():(a.output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(qc,budget=result['budget'],steps=result['steps'])))
if __name__=='__main__':main()
