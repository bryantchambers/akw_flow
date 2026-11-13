"""Continuous native-resolution local-inertial raster solver.

Display/storage tiles do not partition the hydraulic domain. Fixed geometry,
closed crop/no-data boundaries, donor-limited conservative water/unit tracer.
"""
import time
import numpy as np
from numba import njit, prange, set_num_threads

G=9.80665


@njit(parallel=True,cache=True)
def momentum(z,h,qx,qy,dt,dx,n,dry):
    rows,cols=z.shape
    for r in prange(rows):
        for c in range(cols):
            za=z[r,c]
            if not np.isfinite(za):
                qx[r,c]=0; qy[r,c]=0;continue
            eta=za+h[r,c]
            if c+1<cols and np.isfinite(z[r,c+1]):
                zb=z[r,c+1]; eb=zb+h[r,c+1]; d=max(eta,eb)-max(za,zb)
                if d>dry and (eta!=eb or qx[r,c]!=0):
                    q=qx[r,c]
                    predictor=q+G*d*dt*(eta-eb)/dx
                    alpha=G*n*n*dt/d**(7/3)
                    qx[r,c]=2*predictor/(1+np.sqrt(1+4*alpha*abs(predictor)))
                else:qx[r,c]=0
            else:qx[r,c]=0
            if r+1<rows and np.isfinite(z[r+1,c]):
                zb=z[r+1,c]; eb=zb+h[r+1,c]; d=max(eta,eb)-max(za,zb)
                if d>dry and (eta!=eb or qy[r,c]!=0):
                    q=qy[r,c]
                    predictor=q+G*d*dt*(eta-eb)/dx
                    alpha=G*n*n*dt/d**(7/3)
                    qy[r,c]=2*predictor/(1+np.sqrt(1+4*alpha*abs(predictor)))
                else:qy[r,c]=0
            else:qy[r,c]=0


@njit(parallel=True,cache=True)
def donor_scales(h,qx,qy,scale,dt,dx):
    rows,cols=h.shape
    for r in prange(rows):
        for c in range(cols):
            out=max(0.,qx[r,c])+max(0.,qy[r,c])
            if c:out+=max(0.,-qx[r,c-1])
            if r:out+=max(0.,-qy[r-1,c])
            scale[r,c]=min(1.,h[r,c]*dx/(dt*out)) if out>0 else 1.


@njit(parallel=True,cache=True)
def limit_faces(qx,qy,scale):
    rows,cols=scale.shape
    for r in prange(rows):
        for c in range(cols):
            if c+1<cols:qx[r,c]*=scale[r,c] if qx[r,c]>=0 else scale[r,c+1]
            if r+1<rows:qy[r,c]*=scale[r,c] if qy[r,c]>=0 else scale[r+1,c]


@njit(inline='always')
def concentration(m,h):
    return m/h if h>1e-12 else 0.


@njit(parallel=True,cache=True)
def update(z,h,m,qx,qy,hn,mn,dt,dx,rain,infil,rowsums):
    rows,cols=h.shape
    for r in prange(rows):
        sv=0.; sm=0.; lossvolume=0.; lossmass=0.; maxh=0.; maxspeed=0.; wet=0
        for c in range(cols):
            if not np.isfinite(z[r,c]):hn[r,c]=0;mn[r,c]=0;continue
            hc=h[r,c];mc=m[r,c]; cc=concentration(mc,hc)
            right=qx[r,c];south=qy[r,c]
            left=qx[r,c-1] if c else 0.
            north=qy[r-1,c] if r else 0.
            mr=right*(cc if right>=0 or c+1==cols else concentration(m[r,c+1],h[r,c+1]))
            ms=south*(cc if south>=0 or r+1==rows else concentration(m[r+1,c],h[r+1,c]))
            ml=left*(concentration(m[r,c-1],h[r,c-1]) if left>=0 and c else cc)
            mt=north*(concentration(m[r-1,c],h[r-1,c]) if north>=0 and r else cc)
            hh=max(0.,hc+dt/dx*(left+north-right-south)+rain*dt)
            mm=max(0.,mc+dt/dx*(ml+mt-mr-ms))
            loss=min(hh,infil*dt) if hh>0 else 0.
            removed=loss*concentration(mm,hh)
            hh-=loss;mm-=removed
            hn[r,c]=hh;mn[r,c]=mm
            sv+=hh;sm+=mm;lossvolume+=loss;lossmass+=removed
            maxh=max(maxh,hh)
            if hh>1e-4:
                speed=max(abs(left),abs(right),abs(north),abs(south))/hh
                maxspeed=max(maxspeed,speed)
            if hh>1e-3:wet+=1
        rowsums[r,0]=sv;rowsums[r,1]=sm;rowsums[r,2]=lossvolume;rowsums[r,3]=lossmass
        rowsums[r,4]=maxh;rowsums[r,5]=maxspeed;rowsums[r,6]=wet


def parameters(config):
    keys={'spacing_m':.5,'duration_s':30.,'dt_max_s':.1,'manning_n':.05,'cfl':.35,'rainfall_mm_hr':0.,'infiltration_mm_hr':0.,'dry_depth_m':1e-6}
    p={k:float(config.get(k,v)) for k,v in keys.items()}
    if not np.isfinite(list(p.values())).all() or min(p[k] for k in ('spacing_m','duration_s','dt_max_s','manning_n','cfl'))<=0 or p['cfl']>.5 or min(p[k] for k in ('rainfall_mm_hr','infiltration_mm_hr','dry_depth_m'))<0:
        raise ValueError('Invalid native simulation parameters')
    if config.get('groundwater',{}).get('enabled') or config.get('stage_boundaries'):raise ValueError('Regional native engine does not yet support groundwater or stage boundaries')
    threads=int(config.get('threads',8))
    if not 1<=threads<=40:raise ValueError('Use 1..40 threads')
    return p


def simulate_cpu(z,initial_depth,config,initial_concentration=None,callback=None):
    total_started=time.monotonic()
    if z.ndim!=2 or z.shape!=initial_depth.shape or z.size==0:raise ValueError('Matching nonempty 2D terrain/depth required')
    p=parameters(config)
    threads=int(config.get('threads',8))
    if not 1<=threads<=40:raise ValueError('Use 1..40 threads')
    set_num_threads(threads)
    z=np.asarray(z,dtype=np.float32)
    h=np.asarray(initial_depth,dtype=np.float64).copy()
    if not np.isfinite(h).all() or np.any(h<0):raise ValueError('Finite nonnegative initial depth required')
    h[~np.isfinite(z)]=0
    if initial_concentration is None:m=np.zeros_like(h)
    else:
        c=np.asarray(initial_concentration)
        if c.shape!=h.shape or not np.isfinite(c).all() or np.any(c<0):raise ValueError('Invalid tracer concentration')
        m=h*c
    qx=np.zeros_like(h);qy=np.zeros_like(h);hn=np.empty_like(h);mn=np.empty_like(h);scale=np.empty(z.shape,np.float64)
    rowsums=np.zeros((z.shape[0],7),float)
    dx=p['spacing_m'];da=dx*dx
    initial=float(h.sum(dtype=np.float64)*da); initialmass=float(m.sum(dtype=np.float64)*da)
    validcount=int(np.count_nonzero(np.isfinite(z)))
    t=0.;steps=0;rainnet=0.;infilnet=0.;massloss=0.;history=[];started=time.monotonic();last_report=-1e30
    maxh=float(np.max(h)); maxspeed=0.
    while t<p['duration_s']-1e-10:
        dt=min(p['dt_max_s'],p['duration_s']-t,p['cfl']*dx/np.sqrt(G*max(maxh,1e-6)))
        if not np.isfinite(dt) or dt<1e-8:raise ValueError('Native timestep collapsed; inspect geometry / forcing')
        momentum(z,h,qx,qy,dt,dx,p['manning_n'],p['dry_depth_m'])
        donor_scales(h,qx,qy,scale,dt,dx);limit_faces(qx,qy,scale)
        update(z,h,m,qx,qy,hn,mn,dt,dx,p['rainfall_mm_hr']/3.6e6,p['infiltration_mm_hr']/3.6e6,rowsums)
        h,hn=hn,h;m,mn=mn,m
        maxh=float(rowsums[:,4].max());maxspeed=float(rowsums[:,5].max())
        rainnet+=p['rainfall_mm_hr']/3.6e6*dt*validcount*da
        infilnet+=float(rowsums[:,2].sum()*da);massloss+=float(rowsums[:,3].sum()*da)
        t+=dt;steps+=1
        if steps>int(config.get('max_steps',200000)):raise ValueError('Native step limit reached')
        if time.monotonic()-last_report>=float(config.get('progress_interval_wall_s',10)) or t>=p['duration_s']-1e-10:
            volume=float(rowsums[:,0].sum()*da);mass=float(rowsums[:,1].sum()*da)
            record={'time_s':t,'duration_s':p['duration_s'],'steps':steps,'dt_s':dt,'maximum_depth_m':maxh,'maximum_speed_proxy_m_s':maxspeed,'wet_cells':int(rowsums[:,6].sum()),'water_volume_m3':volume,'unit_tracer_mass':mass,'water_residual_m3':initial+rainnet-infilnet-volume,'tracer_residual':initialmass-massloss-mass,'wall_s':time.monotonic()-started}
            history.append(record)
            if callback:callback(record)
            last_report=time.monotonic()
    solver_s=time.monotonic()-started
    return {'execution':{'backend':'cpu','threads':threads,'precision':'float64 hydraulic state and donor scales; float32 terrain','solver_s':solver_s,'setup_s':started-total_started,'total_s':time.monotonic()-total_started},'depth':h,'momentum_depth':hn,'face_depth_time_s':t-dt,'mass_per_area':m,'qx_per_width':qx,'qy_per_width':qy,'history':history,'steps':steps,
        'budget':{'initial_volume_m3':initial,'rainfall_m3':rainnet,'infiltration_loss_m3':infilnet,'final_volume_m3':float(rowsums[:,0].sum()*da),'residual_m3':initial+rainnet-infilnet-float(rowsums[:,0].sum()*da)},
        'tracer_budget':{'initial_mass':initialmass,'infiltration_loss':massloss,'final_mass':float(rowsums[:,1].sum()*da),'residual':initialmass-massloss-float(rowsums[:,1].sum()*da)}}


def gpu_available():
    """Optional maintained CUDA provider; CPU-only installations remain usable."""
    import importlib.metadata
    try:
        importlib.metadata.version('numba-cuda')
    except importlib.metadata.PackageNotFoundError:
        return False
    from numba import cuda
    return cuda.is_available()


def simulate(z,initial_depth,config,initial_concentration=None,callback=None):
    """Prefer a visible CUDA GPU; explicit GPU requests never fall back to CPU."""
    backend=config.get('backend','auto')
    if backend not in ('auto','cpu','gpu'):raise ValueError('backend must be auto, cpu or gpu')
    if backend=='gpu' or (backend=='auto' and gpu_available()):
        if not gpu_available():raise RuntimeError('CUDA GPU unavailable; request a Slurm GPU allocation and use the GPU environment')
        from .native_gpu import simulate as simulate_gpu
        return simulate_gpu(z,initial_depth,config,initial_concentration,callback)
    return simulate_cpu(z,initial_depth,config,initial_concentration,callback)
