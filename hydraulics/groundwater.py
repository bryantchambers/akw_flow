"""Optional saturated groundwater columns beneath network cells; SI units.
No unsaturated-zone/Richards solution or regional aquifer reconstruction.
"""
import numpy as np


class Groundwater:
    def __init__(self, nodes, edges, config):
        self.config=config
        n=len(nodes)
        def field(key, minimum=0, positive=False):
            a=np.broadcast_to(np.asarray(config[key],float),(n,)).copy()
            if not np.isfinite(a).all() or (a<minimum).any() or positive and (a<=minimum).any():raise ValueError('Invalid groundwater '+key)
            return a
        self.porosity=field('porosity',positive=True)
        self.sy=field('specific_yield',positive=True)
        if (self.porosity>1).any() or (self.sy>self.porosity).any():raise ValueError('Require 0 < specific_yield <= porosity <= 1')
        mode=config['conductivity_mode']
        if mode=='hydraulic_conductivity':self.k=field('hydraulic_conductivity_m_s')
        elif mode=='intrinsic_permeability':
            self.k=field('intrinsic_permeability_m2')*field('water_density_kg_m3',positive=True)*9.80665/field('dynamic_viscosity_pa_s',positive=True)
        else:raise ValueError('Unknown groundwater conductivity_mode')
        self.area=field('column_area_m2',positive=True)
        bed=np.array([x['bed_elevation_m'] for x in nodes])
        self.bottom=bed-field('aquifer_base_depth_m',positive=True)
        offset=np.broadcast_to(np.asarray(config['initial_head_relative_to_bed_m'],float),(n,))
        head=bed+offset
        if not np.isfinite(head).all() or (head<=self.bottom).any():raise ValueError('Initial groundwater head must exceed aquifer base')
        self.storage_coefficient=self.area*self.sy
        self.volume=(head-self.bottom)*self.storage_coefficient
        self.initial=float(self.volume.sum())
        self.bed_conductance=field('bed_hydraulic_conductivity_m_s')/field('bed_thickness_m',positive=True)*np.array([x['storage_area_m2'] for x in nodes])
        self.endpoints=edges
        self.cumulative_net_exchange=0.

    def tendencies(self, stage, surface_volume):
        head=self.bottom+self.volume/self.storage_coefficient
        q=self.bed_conductance*(stage-head)
        # A dry surface cannot leak water; groundwater may still discharge into it.
        q=np.where((surface_volume<=0)&(q>0),0,q)
        dg=q.copy();throughput=self.bed_conductance.copy()
        for a,b,length,width in self.endpoints:
            thickness=max(0,min(head[a]-self.bottom[a],head[b]-self.bottom[b]))
            k=0 if self.k[a]+self.k[b]==0 else 2*self.k[a]*self.k[b]/(self.k[a]+self.k[b])
            conductance=k*thickness*width/length
            flux=conductance*(head[a]-head[b]);dg[a]-=flux;dg[b]+=flux
            throughput[a]+=conductance;throughput[b]+=conductance
        active=throughput>0
        limit=float(np.min(.25*self.storage_coefficient[active]/throughput[active])) if active.any() else float('inf')
        return -q,dg,q,head,limit
