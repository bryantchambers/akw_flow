"""Cross-section integration of staggered native 2D fluxes into candidate reaches.

A reach is geometry, not a prescribed 1D conveyance link. A snapshot can show
bidirectional/transient exchange; it does not establish a steady directed graph.
"""
import math
import numpy as np
from scipy.ndimage import map_coordinates
from shapely.geometry import LineString,Point
from rasterio.windows import Window


def section_geometry(line,water_polygon,fraction=.5,half_length=1000):
    d=line.length*fraction;epsilon=min(1.,line.length/4)
    a=line.interpolate(max(0.,d-epsilon));b=line.interpolate(min(line.length,d+epsilon))
    dx=b.x-a.x;dy=b.y-a.y;norm=math.hypot(dx,dy)
    if norm<1e-9:return None,None,False
    tangent=np.array([dx/norm,dy/norm]);p=line.interpolate(d);n=np.array([-tangent[1],tangent[0]])
    section=LineString([(p.x-n[0]*half_length,p.y-n[1]*half_length),(p.x+n[0]*half_length,p.y+n[1]*half_length)])
    clipped=water_polygon.intersection(section)
    parts=list(clipped.geoms) if hasattr(clipped,'geoms') else [clipped]
    candidates=[g for g in parts if g.geom_type=='LineString' and g.distance(p)<1e-5 and g.length>0]
    if not candidates:return None,None,False
    section=max(candidates,key=lambda g:g.length)
    # A one-sided truncation also invalidates the complete-cross-section estimate.
    full_ends=[Point(p.x-n[0]*half_length,p.y-n[1]*half_length),Point(p.x+n[0]*half_length,p.y+n[1]*half_length)]
    capped=any(end.distance(section)<1e-6 for end in full_ends)
    return section,tangent,capped


def integrate_section(dataset,section,tangent):
    """Midpoint quadrature at <=0.5 m. Flux component sampling respects face offsets."""
    count=max(1,int(math.ceil(section.length/dataset.res[0])))
    points=[section.interpolate((i+.5)/count,normalized=True) for i in range(count)]
    xs=np.array([p.x for p in points]);ys=np.array([p.y for p in points]);cc,rr=(~dataset.transform) @ (xs,ys)
    c0=max(0,int(np.floor(cc.min()))-2);r0=max(0,int(np.floor(rr.min()))-2)
    c1=min(dataset.width,int(np.ceil(cc.max()))+2);r1=min(dataset.height,int(np.ceil(rr.max()))+2)
    if c0>=c1 or r0>=r1:return {'valid':False,'reason':'outside survey'}
    a=dataset.read((1,2,3),window=Window(c0,r0,c1-c0,r1-r0)).astype(float)
    a[a==dataset.nodata]=np.nan
    depth=map_coordinates(a[0],[rr-r0-.5,cc-c0-.5],order=1,mode='constant',cval=np.nan,prefilter=False)
    qx=map_coordinates(a[1],[rr-r0-.5,cc-c0-1.],order=1,mode='constant',cval=np.nan,prefilter=False)
    qy=map_coordinates(a[2],[rr-r0-1.,cc-c0-.5],order=1,mode='constant',cval=np.nan,prefilter=False)
    valid=np.isfinite(depth)&np.isfinite(qx)&np.isfinite(qy)
    if not valid.all():return {'valid':False,'reason':'cross-section extends beyond valid terrain','valid_fraction':float(valid.mean())}
    ds=section.length/count;area=float(depth.sum()*ds)
    return {'valid':True,'discharge_m3_s':float(((qx*tangent[0]-qy*tangent[1])*ds).sum()),
        'wetted_area_m2':area,'mapped_width_m':section.length,'mean_depth_m':float(depth.mean()),
        'wet_width_m':float(np.count_nonzero(depth>.001)*ds),'quadrature_spacing_m':ds}
