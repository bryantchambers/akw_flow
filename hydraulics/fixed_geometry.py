"""Evidence-labelled fixed geometry and water-level scenarios; no source edits."""
import math
import numpy as np
from rasterio.features import geometry_mask,bounds
from rasterio.windows import from_bounds,Window,transform as window_transform


def patches(shape,transform,records):
    """Yield small native-grid masks; preserve grid alignment and original no-data."""
    for record in records:
        if not isinstance(record.get('evidence'),str) or not record['evidence'].strip():raise ValueError('Scenario edit requires evidence or rationale')
        geometry=record['geometry_projected']
        if geometry.get('type') not in ('Polygon','MultiPolygon'):raise ValueError('Scenario geometry must be a projected polygon')
        window=from_bounds(*bounds(geometry),transform=transform)
        r0=max(0,int(math.floor(window.row_off)));c0=max(0,int(math.floor(window.col_off)))
        r1=min(shape[0],int(math.ceil(window.row_off+window.height)));c1=min(shape[1],int(math.ceil(window.col_off+window.width)))
        if r0>=r1 or c0>=c1:continue
        window=Window(c0,r0,c1-c0,r1-r0)
        mask=geometry_mask([geometry],out_shape=(r1-r0,c1-c0),transform=window_transform(window,transform),invert=True)
        yield record,np.s_[r0:r1,c0:c1],mask


def apply_fixed_edits(elevation,transform,records):
    """Modify scenario array in place, never fill source no-data or change spacing."""
    for record in records:
        if record.get('mode') not in ('set','lower','raise') or not math.isfinite(float(record['elevation_m'])):raise ValueError('Invalid fixed terrain edit')
    for record,section,mask in patches(elevation.shape,transform,records):
        values=elevation[section];mask &= np.isfinite(values);level=float(record['elevation_m'])
        if record['mode']=='set':values[mask]=level
        elif record['mode']=='lower':values[mask]=np.minimum(values[mask],level)
        else:values[mask]=np.maximum(values[mask],level)


def apply_initial_levels(depth,elevation,water,transform,records):
    """Set initial stage in polygon, default restricted to mapped water; last edit wins."""
    for record in records:
        if not math.isfinite(float(record['stage_m'])):raise ValueError('Invalid initial stage')
        if not isinstance(record.get('mapped_water_only',True),bool):raise ValueError('mapped_water_only must be boolean')
    for record,section,mask in patches(depth.shape,transform,records):
        z=elevation[section];mask &= np.isfinite(z)
        if record.get('mapped_water_only',True):mask &= water[section]>0
        h=depth[section];h[mask]=np.maximum(float(record['stage_m'])-z[mask],0)
