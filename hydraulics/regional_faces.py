"""Native cell-face inspection and honest multiscale display selections."""
import json,math
import numpy as np
import rasterio
from rasterio.windows import Window,from_bounds
from . import regional_view as view
from .face_index import reduce_records


def faces(bounds,snapshot='final',minimum_q=1e-5,include_idle=False,target_faces=1400):
    if len(bounds)!=4 or not np.isfinite(bounds).all():raise ValueError('Invalid bounds')
    west,south,east,north=map(float,bounds)
    if not -180<=west<east<=180 or not -85<=south<north<=85:raise ValueError('Invalid bounds')
    if not np.isfinite(minimum_q) or minimum_q<0 or not 100<=target_faces<=12000:raise ValueError('Invalid face display settings')
    if snapshot not in ('initial','final'):raise ValueError('Unknown snapshot')
    xs,ys=view.TOUTM.transform([west,east,east,west],[south,south,north,north])
    if not np.isfinite([xs,ys]).all():raise ValueError('Bounds cannot be projected')
    path=view.raster_path('depth',snapshot)
    with rasterio.open(path) as src:
        tf=src.transform;dx=src.res[0]
        x0=max(min(xs),src.bounds.left);x1=min(max(xs),src.bounds.right);y0=max(min(ys),src.bounds.bottom);y1=min(max(ys),src.bounds.top)
        empty={'mode':'outside','faces':[],'grid_lines':[],'solver_spacing_m':dx,'message':'Outside survey footprint'}
        if x0>=x1 or y0>=y1:return empty
        w=from_bounds(x0,y0,x1,y1,tf)
        r0=max(0,math.floor(w.row_off));c0=max(0,math.floor(w.col_off));r1=min(src.height,math.ceil(w.row_off+w.height));c1=min(src.width,math.ceil(w.col_off+w.width))
        nr,nc=r1-r0,c1-c0
        detail=nr*nc<=6000
        grid=[]
        if detail and nr+nc<=250:
            for c in range(c0,c1+1):grid.append([list(view.TOGEO.transform(*(tf @ (c,r0)))),list(view.TOGEO.transform(*(tf @ (c,r1))))])
            for r in range(r0,r1+1):grid.append([list(view.TOGEO.transform(*(tf @ (c0,r)))),list(view.TOGEO.transform(*(tf @ (c1,r))))])
        if snapshot=='initial':return {'mode':'native' if detail else 'overview','faces':[],'grid_lines':grid,'solver_spacing_m':dx,'message':'Initial velocities are zero; select final state for computed flow.'}
        if detail:
            h=min(nr+1,src.height-r0);w=min(nc+1,src.width-c0)
            a=src.read((1,2,3),window=Window(c0,r0,w,h));records=[]
            rr,cc=np.indices((nr,nc));rr+=r0;cc+=c0
            for orientation,band in [('east',1),('south',2)]:
                q=a[band,:nr,:nc]*dx
                valid=a[0,:nr,:nc]>=0
                if orientation=='east':
                    count=min(nc,src.width-c0-1);valid[:,count:]=False
                    valid[:,:count] &= a[0,:nr,1:count+1]>=0
                else:
                    count=min(nr,src.height-r0-1);valid[count:]=False
                    valid[:count] &= a[0,1:count+1,:nc]>=0
                if not include_idle:valid &= np.abs(q)>max(minimum_q,1e-15)
                for r,c,value in zip(rr[valid],cc[valid],q[valid]):records.append((orientation,int(r),int(c),float(value)))
            mode='native';message='All qualifying native faces in this view; grey faces have no displayed flow.'
        else:
            meta=view.output_directory()/'face_index.json'
            if not meta.exists():return {'mode':'index_pending','faces':[],'grid_lines':[],'solver_spacing_m':dx,'message':'Overview face index is being prepared. Native face inspection is available when zoomed in.'}
            info=json.loads(meta.read_text())
            if info['source_state']!={'size':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns}:raise ValueError('Overview face index is stale; rebuild before viewing')
            desired=max(1,math.sqrt(nr*nc/(target_faces/2)))
            factor=max((f for f in info['factors'] if f<=desired),default=min(info['factors']))
            ir0=r0//factor;ic0=c0//factor;ir1=math.ceil(r1/factor);ic1=math.ceil(c1/factor)
            with rasterio.open(view.output_directory()/f'faces_{factor}.tif') as index:
                a=index.read(window=Window(ic0,ir0,ic1-ic0,ir1-ir0))
            ratio=max(1,math.ceil(math.sqrt(a.shape[1]*a.shape[2]/(target_faces/2))))
            records=[]
            for offset,orientation in ((0,'east'),(3,'south')):
                data=a[offset:offset+3].copy()
                valid=(data[1]>=r0)&(data[1]<r1)&(data[2]>=c0)&(data[2]<c1)
                data[1,~valid]=-1
                reduced=reduce_records(data,ratio)
                valid=(reduced[1]>=0)&(abs(reduced[0])*dx>max(minimum_q,1e-15))
                for q,r,c in zip(reduced[0,valid],reduced[1,valid],reduced[2,valid]):records.append((orientation,int(r),int(c),float(q*dx)))
            mode='representative';message='Strongest real native face in each display bin, separately east/south; not a summed coarse flow or a complete reach network.'
    result=[]
    for orientation,r,c,q in records:
        if orientation=='east':
            face=[tf @ (c+1,r),tf @ (c+1,r+1)];aa=tf @ (c+.5,r+.5);bb=tf @ (c+1.5,r+.5)
        else:
            face=[tf @ (c,r+1),tf @ (c+1,r+1)];aa=tf @ (c+.5,r+.5);bb=tf @ (c+.5,r+1.5)
        result.append({'id':f'r{r}c{c}:{orientation}','row':r,'col':c,'orientation':orientation,'discharge_m3_s':q,
            'face_coordinates':[list(view.TOGEO.transform(*p)) for p in face],
            'from_coordinates':list(view.TOGEO.transform(*aa)),'to_coordinates':list(view.TOGEO.transform(*bb))})
    return {'mode':mode,'faces':result,'grid_lines':grid,'native_cells_in_view':nr*nc,'solver_spacing_m':dx,'minimum_q_m3_s':minimum_q,'message':message}
