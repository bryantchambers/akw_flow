"""Diffusion-wave storage network; excludes momentum/inertial and structure equations."""
import math
import numpy as np


def positive(value, name, allow_zero=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f'{name} must be finite and positive')
    return value


def discharge(depth_m, width_m, slope, manning_n, viscosity_m2_s=1e-6, closure='manning', transition_re=500):
    """Signed discharge. Reynolds uses hydraulic radius (not hydraulic diameter).

    Laminar wide rectangular sheet: u=g*h²*S/(3*nu). Auto is restricted to
    width/depth >=20; transitional region linearly blends constitutive velocities.
    This blend is a numerical scenario option, not a validated universal law.
    """
    h=positive(depth_m,'depth',True); b=positive(width_m,'width'); n=positive(manning_n,'Manning n')
    nu=positive(viscosity_m2_s,'viscosity'); threshold=positive(transition_re,'transition Re')
    if closure not in ('manning','laminar_wide','auto_wide'): raise ValueError('Unknown friction closure')
    if not math.isfinite(slope): raise ValueError('Nonfinite slope')
    if h == 0 or slope == 0: return dict(flow_m3_s=0.,velocity_m_s=0.,reynolds_R=0.,froude=0.,area_m2=b*h,regime='stationary')
    radius=b*h/(b+2*h); s=abs(slope)
    ut=radius**(2/3)*math.sqrt(s)/n
    ul=9.80665*h*h*s/(3*nu)
    if closure != 'manning' and b/h < 20: raise ValueError('Wide laminar closure requires width/depth >=20')
    u=ut
    if closure == 'laminar_wide': u=ul
    if closure == 'auto_wide':
        rel=ul*radius/nu
        blend=min(1.,max(0.,(rel-threshold)/(3*threshold)))
        u=ul*(1-blend)+ut*blend
    re=u*radius/nu
    regime='laminar' if re<threshold else ('transitional' if re<4*threshold else 'turbulent')
    sign=1 if slope>0 else -1
    return dict(flow_m3_s=sign*b*h*u,velocity_m_s=sign*u,reynolds_R=re,froude=u/math.sqrt(9.80665*h),area_m2=b*h,regime=regime)


def simulate(network, config):
    nodes=network['nodes']; edges=network['edges']; n=len(nodes)
    if not n or n>50000: raise ValueError('Require 1..50000 nodes')
    ids=[x['id'] for x in nodes]
    if len(set(ids))!=n: raise ValueError('Duplicate node IDs')
    ix={key:i for i,key in enumerate(ids)}
    bed=np.array([float(x['bed_elevation_m']) for x in nodes])
    area=np.array([positive(x['storage_area_m2'],'storage area') for x in nodes])
    v=area*np.array([positive(x.get('initial_depth_m',config.get('initial_depth_m',0.1)),'initial depth',True) for x in nodes])
    if not np.isfinite(bed).all(): raise ValueError('Invalid bed')
    source=np.asarray(config.get('external_flows_m3_s',[0]*n),float)
    if source.shape!=(n,) or not np.isfinite(source).all(): raise ValueError('external_flows_m3_s must match nodes')
    duration=positive(config.get('duration_s',60),'duration'); dtmax=positive(config.get('dt_max_s',0.1),'dt max')
    interval=positive(config.get('output_interval_s',10),'output interval')
    roughness=config.get('roughness',{}); overrides=config.get('edge_overrides',{})
    endpoint=[]; params=[]
    for e in edges:
        a,b=ix[e['from']],ix[e['to']]
        if a==b: raise ValueError('Self loop')
        endpoint.append((a,b))
        p=dict(e); p.update(roughness);p.update(overrides.get(e['id'],{}))
        p['length_m']=positive(p['length_m'],'length'); p['width_m']=positive(p['width_m'],'width')
        p['manning_n']=positive(p.get('manning_n',0.035),'Manning n');params.append(p)
    def flux():
        stage=bed+v/area; qs=[]; ds=[]
        for (a,b),p in zip(endpoint,params):
            # A shared high bed prevents flow through an unresolved terrain barrier.
            depth=max(0.,max(stage[a],stage[b])-max(bed[a],bed[b]))
            d=discharge(depth,p['width_m'],(stage[a]-stage[b])/p['length_m'],p['manning_n'],p.get('viscosity_m2_s',1e-6),p.get('closure','manning'),p.get('transition_re',500))
            qs.append(d['flow_m3_s']);ds.append(d)
        return np.array(qs),ds
    t=0.; step=0; initial=float(v.sum()); ext=0.; samples=[]; nextout=0.; flux_integral=np.zeros(len(edges)); last_output=0.
    while True:
        q,diag=flux()
        if t>=nextout-1e-10 or t>=duration-1e-10:
            samples.append(dict(time_s=t,volumes_m3=v.tolist(),flows_m3_s=q.tolist(),cross_sections_m2=[d['area_m2'] for d in diag],preceding_interval_mean_flows_m3_s=(flux_integral/(t-last_output)).tolist() if t>last_output else q.tolist()))
            flux_integral[:]=0.;last_output=t
            nextout+=interval
        if t>=duration-1e-10: break
        dv=source.copy(); outgoing=np.maximum(-source,0)
        for (a,b),flow in zip(endpoint,q):
            dv[a]-=flow;dv[b]+=flow
            outgoing[a if flow>=0 else b]+=abs(flow)
        active=outgoing>0
        if np.any(active & (v<=0)): raise ValueError('Outflow requested from dry storage')
        dt=min(dtmax,duration-t,nextout-t,float(np.min(0.15*v[active]/outgoing[active])) if active.any() else dtmax)
        if dt<1e-12: raise ValueError('Step too small; revise boundary/geometry')
        flux_integral+=dt*q
        v+=dt*dv;ext+=dt*float(source.sum());t+=dt;step+=1
        if step>int(config.get('max_steps',200000)): raise ValueError('Maximum steps exceeded')
        if not np.isfinite(v).all() or (v<0).any(): raise ValueError('Invalid storage')
    return dict(nodes=nodes,edges=edges,external_flows_m3_s=source.tolist(),model='diffusion-wave storage network',assumptions=network.get('assumptions',[]),node_ids=ids,edge_ids=[e['id'] for e in edges],samples=samples,final_diagnostics=diag,steps=step,budget={'initial_volume_m3':initial,'external_net_m3':ext,'final_volume_m3':float(v.sum()),'residual_m3':initial+ext-float(v.sum())})


def output_geojson(network,result):
    byid={n['id']:n for n in network['nodes']}
    return {'type':'FeatureCollection','model':{'name':'Exploratory diffusion-wave storage network','scenario':'Hypothetical depth and roughness; uncalibrated terrain candidates','metric':'signed discharge','unit':'m3/s'},'features':[{'type':'Feature','geometry':{'type':'LineString','coordinates':[byid[e['from']]['coordinates'],byid[e['to']]['coordinates']]},'properties':{'id':e['id'],'value':d['flow_m3_s'],**d}} for e,d in zip(network['edges'],result['final_diagnostics'])]}
