"""Mesh-sensitivity diagnostics. Screening indicators, not archaeological bank labels."""
import numpy as np
from scipy.ndimage import label


def disconnected_pools(patch, stage, pixel_area=.25, minimum_pool_area_m2=1.):
    wet=np.isfinite(patch)&(patch<stage)
    labels,n=label(wet)  # four-neighbour hydraulic topology, no diagonal shortcuts
    areas=np.bincount(labels.ravel(),minlength=n+1)[1:]*pixel_area
    kept=areas[areas>=minimum_pool_area_m2]
    return {'pool_count':int(len(kept)),'secondary_pool_area_m2':float(kept.sum()-kept.max()) if len(kept) else 0.,'wet_area_m2':float(wet.sum()*pixel_area)}


def aggregate_nested(coarse, fine):
    """Conservative depth and water-volume weighted tracer on a complete nested grid."""
    ratio=int(round(coarse['parameters']['grid_spacing_m']/fine['parameters']['grid_spacing_m']))
    if ratio<1 or not np.isclose(ratio*fine['parameters']['grid_spacing_m'],coarse['parameters']['grid_spacing_m']):raise ValueError('Non-nested spacings')
    coarse_lookup={n['id'].split(':')[-1]:i for i,n in enumerate(coarse['nodes'])}
    groups=[[] for _ in coarse['nodes']]
    for i,node in enumerate(fine['nodes']):
        suffix=node['id'].split(':')[-1];r,c=map(int,suffix[1:].split('c'))
        key=f'r{r//ratio}c{c//ratio}'
        if key in coarse_lookup:groups[coarse_lookup[key]].append(i)
    if any(len(g)!=ratio**2 for g in groups):raise ValueError('Require complete matching nested terrain support')
    groups=np.asarray(groups,int)
    output=[]
    for cf,ff in zip(coarse['frames'],fine['frames']):
        if not np.isclose(cf['time_s'],ff['time_s']):raise ValueError('Nonmatching times')
        h=np.asarray(ff['depth_m'])[groups];c=np.asarray(ff['tracer_concentration'])[groups]
        depth=h.mean(axis=1);volume=h.sum(axis=1)
        concentration=np.divide((h*c).sum(axis=1),volume,out=np.zeros_like(volume),where=volume>1e-12)
        output.append({'time_s':cf['time_s'],'fine_depth_m':depth.tolist(),'fine_tracer_concentration':concentration.tolist(),
            'depth_difference_m':(depth-np.asarray(cf['depth_m'])).tolist(),
            'tracer_difference':(concentration-np.asarray(cf['tracer_concentration'])).tolist()})
    if len(output)!=len(coarse['frames']) or len(output)!=len(fine['frames']):raise ValueError('Mismatched frame counts')
    return output
