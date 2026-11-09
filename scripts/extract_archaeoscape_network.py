#!/usr/bin/env python3
"""Extract anonymous, parcel-local terrain candidates from an authorized DTM.
Never interprets source coordinates as geographic locations. No georeferencing.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy import ndimage

NEIGHBOURS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]


def positive(value, name, zero=False):
    v = float(value)
    if not math.isfinite(v) or v < 0 or (v == 0 and not zero):
        raise ValueError(f'{name} must be finite and positive (or zero if allowed)')
    return v


def extract(z, config):
    """Strict downhill D8 + local depression, without pit filling or gap bridging.

    Candidate membership is scenario-dependent, not an archaeological probability.
    Entire raster window must be a single anonymous parcel with known metric units.
    """
    z = np.array(z, dtype=float, copy=True)
    if z.ndim != 2 or min(z.shape) < 3 or z.size > int(config.get('max_window_cells', 262144)):
        raise ValueError('Use a 2D window >=3x3 within max_window_cells')
    spacing = positive(config['pixel_size_m'], 'pixel_size_m')
    sigma = positive(config.get('smoothing_sigma_m', 0), 'smoothing_sigma_m', True) / spacing
    radius = int(math.ceil(positive(config['relief_radius_m'], 'relief_radius_m') / spacing))
    if 2 * radius + 1 > min(z.shape):
        raise ValueError('Relief radius exceeds available window')
    slope_min = positive(config.get('minimum_downhill_slope', 0), 'minimum_downhill_slope', True)
    depression_min = positive(config.get('minimum_relative_depression_m', 0), 'minimum_relative_depression_m', True)
    area_min = positive(config['minimum_contributing_area_m2'], 'minimum_contributing_area_m2')
    length_min = positive(config.get('minimum_component_length_m', 0), 'minimum_component_length_m', True)
    valid = np.isfinite(z)
    for row, col in config.get('excluded_cells_rc', []):
        if not (0 <= row < z.shape[0] and 0 <= col < z.shape[1]):
            raise ValueError('Excluded cell outside window')
        valid[row, col] = False
    # Constant padding and invalid cells reduce support; no interpolation across holes.
    work = np.where(valid, z, 0.)
    support = valid.copy()
    if sigma:
        truncate = 4.0
        work = ndimage.gaussian_filter(work, sigma, mode='constant', cval=0, truncate=truncate)
        support = ndimage.minimum_filter(valid.astype(np.uint8), size=2*int(truncate*sigma+.5)+1, mode='constant', cval=0).astype(bool)
    width = 2 * radius + 1
    relief_valid = ndimage.minimum_filter(support.astype(np.uint8), size=width, mode='constant', cval=0).astype(bool)
    mean = ndimage.uniform_filter(work, size=width, mode='constant', cval=0.)
    depression = mean - work
    h, w = z.shape
    target = np.full(z.size, -1, dtype=int)
    best = np.full(z.shape, slope_min, dtype=float)
    for dr, dc in NEIGHBOURS:
        r0, r1 = max(0, -dr), min(h, h-dr)
        c0, c1 = max(0, -dc), min(w, w-dc)
        src = (slice(r0,r1), slice(c0,c1)); dst = (slice(r0+dr,r1+dr), slice(c0+dc,c1+dc))
        slopes = (work[src] - work[dst]) / (spacing * math.hypot(dr,dc))
        mask = support[src] & support[dst] & (slopes > best[src])
        # Diagonal links cannot cut across a NoData or excluded corner.
        if dr and dc:
            mask &= support[r0+dr:r1+dr,c0:c1] & support[r0:r1,c0+dc:c1+dc]
        rr, cc = np.nonzero(mask)
        target[(rr+r0)*w+cc+c0] = (rr+r0+dr)*w+cc+c0+dc
        best[src][mask] = slopes[mask]
    acc = np.where(support.ravel(), spacing**2, 0.)
    for i in np.argsort(-work.ravel()):
        if target[i] >= 0:
            acc[target[i]] += acc[i]
    selected = relief_valid.ravel() & (acc >= area_min) & (depression.ravel() >= depression_min) & (target >= 0)
    # Remove short components by total selected link length, using actual graph edges.
    parent = np.arange(z.size)
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    indices = np.flatnonzero(selected)
    for i in indices:
        a,b=find(int(i)),find(int(target[i])); parent[a]=b
    lengths = {}
    for i in indices:
        j=target[i]; length=spacing*math.hypot(i//w-j//w,i%w-j%w)
        key=find(int(i)); lengths[key]=lengths.get(key,0)+length
    indices = [int(i) for i in indices if lengths[find(int(i))] >= length_min]
    used=sorted(set(indices)|{int(target[i]) for i in indices})
    nodes=[{'id':f'n{i}', 'local_xy_m':[(i%w+.5)*spacing,(h-i//w-.5)*spacing],
            'row_col':[i//w,i%w], 'terrain_elevation_m_local':float(work.ravel()[i]),
            'contributing_area_m2':float(acc[i])} for i in used]
    edges=[]
    for i in indices:
        j=int(target[i]); length=spacing*math.hypot(i//w-j//w,i%w-j%w)
        edges.append({'id':f'e{i}', 'from':f'n{i}', 'to':f'n{j}', 'length_m':length,
                      'terrain_slope':float((work.ravel()[i]-work.ravel()[j])/length),
                      'local_depression_m':float(depression.ravel()[i]),
                      'width_m':None,'bed_depth_m':None})
    return {'coordinate_system':'anonymous_local_cartesian_metres','nodes':nodes,'edges':edges,
            'status':'Terrain candidate graph; historical age, bed geometry and connectivity unvalidated',
            'qc':{'input_cells':z.size,'finite_cells':int(valid.sum()),'routing_cells':int(support.sum()),
                  'relief_supported_cells':int(relief_valid.sum()),'candidate_edges':len(edges),
                  'terminal_cells':int(np.sum(support.ravel() & (target<0))),
                  'boundary_note':'Window edges and holes truncate contributing area; no filling or external inflow inferred'}}


def main():
    import rasterio
    from rasterio.windows import Window
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/archaeoscape_extraction.json'))
    p.add_argument('--output',type=Path,default=Path('private_outputs/archaeoscape'))
    p.add_argument('--inspect',action='store_true')
    a=p.parse_args(); config=json.loads(a.config.read_text())
    if not a.output.resolve().is_relative_to((Path(__file__).resolve().parents[1]/'private_outputs').resolve()):
        raise ValueError('Output must remain inside ignored private_outputs/')
    with rasterio.open(a.input) as src:
        if a.inspect:
            print(json.dumps({'bands':src.count,'descriptions':src.descriptions,'dtypes':src.dtypes,
                              'shape':[src.height,src.width],'band_scales':src.scales,'band_offsets':src.offsets,
                              'note':'Coordinates deliberately omitted. Confirm DTM band and elevation encoding with documentation.'}));return
        band=config['dtm_band']
        if type(band) is not int or not 1<=band<=src.count:
            raise ValueError('Set documented dtm_band after --inspect; RGB/labels must not be used as elevation')
        if config.get('relative_elevations_verified') is not True:
            raise ValueError('Confirm normalization preserves metric relative elevations before slope-based extraction')
        scale=positive(config['elevation_scale_to_m'],'elevation_scale_to_m')
        window=config['window']
        if any(type(window[k]) is not int or window[k]<0 for k in ('row_off','col_off','height','width')):
            raise ValueError('Window entries must be nonnegative integers')
        if window['height']*window['width']>config['max_window_cells'] or min(window['height'],window['width'])<3:
            raise ValueError('Window must be >=3x3 and fit max_window_cells')
        if window['row_off']+window['height']>src.height or window['col_off']+window['width']>src.width:
            raise ValueError('Window exceeds input raster')
        raw=src.read(band,window=Window(**window),masked=True).astype(float)
        z=raw.filled(np.nan)*scale
    # The selected raw window hash avoids rereading multi-GB source files.
    provenance={'window_sha256':hashlib.sha256(np.asarray(z,dtype='<f8').tobytes()).hexdigest(),
                'window':window,'dtm_band':band,'elevation_scale_to_m':scale,
                'source':'EFEO Archaeoscape 2024, authorized local parcel',
                'normalization_confirmation':'User confirmed relative metric elevations; retain supporting documentation separately'}
    a.output.mkdir(parents=True,exist_ok=True)
    memberships={};results={}
    for name, profile in config['profiles'].items():
        if not name.replace('_','').isalnum(): raise ValueError('Invalid profile name')
        settings={**config,**profile}; result=extract(z,settings)
        result['parameters']=settings;result['provenance']=provenance
        (a.output/(name+'_network.json')).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        results[name]=result['qc']
        for e in result['edges']:memberships.setdefault(e['id'],[]).append(name)
    summary={'profiles':results,'edge_membership':memberships,
             'interpretation':'Profile agreement is sensitivity persistence, not probability or historical age.'}
    (a.output/'sensitivity.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'status':'completed','profiles':results}))

if __name__=='__main__':main()
