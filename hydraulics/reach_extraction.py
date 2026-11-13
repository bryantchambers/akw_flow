"""Topology from a conduit skeleton; storage bodies never get centroid-spoke edges."""
import math
import numpy as np
from shapely.geometry import LineString


def skeleton_paths(skeleton,traversable=None):
    """Trace every pixel edge once; keep loops, endpoints and actual branch nodes.

    Diagonal edges are omitted if an orthogonal route exists, avoiding false tiny
    triangles at right-angle corners. No nearest-feature gap closure is performed.
    """
    if traversable is not None and traversable.shape!=skeleton.shape:raise ValueError('Mask and skeleton shapes differ')
    rows,cols=skeleton.shape;rr,cc=np.nonzero(skeleton)
    ids=set((rr.astype(np.int64)*cols+cc).tolist());adj={}
    for key in ids:
        r,c=divmod(key,cols);neighbours=[]
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if not (dr or dc):continue
                y,x=r+dr,c+dc
                if not 0<=y<rows or not 0<=x<cols or y*cols+x not in ids:continue
                if dr and dc and (skeleton[r,x] or skeleton[y,c]):continue
                if dr and dc and traversable is not None and not (traversable[r,x] or traversable[y,c]):continue
                neighbours.append(y*cols+x)
        adj[key]=sorted(neighbours)
    visited=set();paths=[]
    def walk(a,b):
        path=[a];previous=a;current=b
        while True:
            visited.add((min(previous,current),max(previous,current)));path.append(current)
            if len(adj[current])!=2 or current==path[0]:break
            nxt=next(x for x in adj[current] if x!=previous)
            if (min(current,nxt),max(current,nxt)) in visited:break
            previous,current=current,nxt
        return path
    for a in sorted(adj):
        if len(adj[a])==2:continue
        for b in adj[a]:
            if (min(a,b),max(a,b)) not in visited:paths.append(walk(a,b))
    for a in sorted(adj):
        for b in adj[a]:
            if (min(a,b),max(a,b)) not in visited:paths.append(walk(a,b))
    return [[divmod(key,cols) for key in path] for path in paths]


def subdivide_path(path,spacing,max_length):
    if max_length<=0:raise ValueError('Positive maximum reach length required')
    part=[path[0]];length=0.;parts=[]
    for point in path[1:]:
        length+=math.hypot(point[0]-part[-1][0],point[1]-part[-1][1])*spacing;part.append(point)
        if length>=max_length:parts.append(part);part=[point];length=0.
    if len(part)>1:parts.append(part)
    return parts
