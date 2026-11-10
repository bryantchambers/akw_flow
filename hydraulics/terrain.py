"""Fixed-geometry, subgrid storage / local-inertial face solver.

Research prototype: no advective momentum, erosion, sediment or organism kinetics.
Arrays are projected metres. Closed perimeter unless explicit stage boundaries supplied.
"""
import numpy as np

G = 9.80665


def storage(stage, elevations, area):
    return np.maximum(np.asarray(stage)[..., None] - elevations, 0).mean(axis=-1) * area


def stage_from_volume(volume, elevations, area):
    """Exact inverse for equal-area, sorted terrain samples, including dry cells."""
    count = elevations.shape[1]
    sums = np.cumsum(elevations, axis=1)
    thresholds = (elevations * np.arange(1, count + 1) - sums) * area / count
    k = (thresholds <= volume[:, None]).sum(axis=1).clip(1, count)
    return (volume * count / area + sums[np.arange(len(k)), k - 1]) / k


def face_geometry(stage_a, stage_b, profiles, strip_width):
    depths = np.maximum(np.maximum(stage_a, stage_b)[:, None] - profiles, 0)
    area = depths.sum(axis=1) * strip_width
    width = (depths > 0).sum(axis=1) * strip_width
    radius = np.divide(area, width, out=np.zeros_like(area), where=width > 0)
    return area, width, radius


def simulate(mesh, config):
    z = np.asarray(mesh['terrain_samples_m'], float)
    profiles = np.asarray(mesh['face_profiles_m'], float)
    a = np.asarray(mesh['face_from'], int); b = np.asarray(mesh['face_to'], int)
    area = float(mesh['cell_area_m2']); dx = float(mesh['spacing_m'])
    n = len(z); nf = len(a)
    if z.ndim != 2 or not n or not np.isfinite(z).all() or np.any(np.diff(z, axis=1) < 0):
        raise ValueError('Require finite sorted terrain samples')
    if profiles.ndim != 2 or len(profiles) != nf or not np.isfinite(profiles).all():
        raise ValueError('Invalid face profiles')
    if np.any(a < 0) or np.any(b < 0) or np.any(a >= n) or np.any(b >= n) or np.any(a == b):
        raise ValueError('Invalid face endpoints')
    duration = float(config.get('duration_s', 600)); dtmax = float(config.get('dt_max_s', 1))
    interval = float(config.get('output_interval_s', 60)); roughness = float(config.get('manning_n', .05))
    if not all(np.isfinite(x) and x > 0 for x in (duration, dtmax, interval, roughness, area, dx)):
        raise ValueError('Invalid positive simulation parameter')
    cfl = float(config.get('cfl', .35))
    if not 0 < cfl <= .5: raise ValueError('cfl must be in (0,.5]')
    eta = np.broadcast_to(np.asarray(config.get('initial_stage_m', z[:, 0]), float), (n,)).copy()
    v = storage(eta, z, area)
    conc = np.broadcast_to(np.asarray(config.get('initial_tracer_concentration', 0.), float), (n,))
    if not np.isfinite(eta).all() or not np.isfinite(conc).all() or np.any(conc < 0): raise ValueError('Invalid initial state')
    mass = v * conc
    rain = float(config.get('rainfall_mm_hr', 0)) / 3.6e6
    infil = float(config.get('infiltration_mm_hr', 0)) / 3.6e6
    if not np.isfinite([rain, infil]).all() or min(rain, infil) < 0: raise ValueError('Invalid rainfall/infiltration')
    # Optional fixed external groundwater head. This is a boundary approximation, not an aquifer solver.
    gw = config.get('groundwater', {})
    conductance = float(gw.get('conductance_m2_s_per_cell', 0)) if gw.get('enabled', False) else 0.
    head = float(gw.get('head_m', 0))
    if not np.isfinite([conductance, head]).all() or conductance < 0: raise ValueError('Invalid groundwater boundary')
    boundaries = config.get('stage_boundaries', [])
    used = set()
    for boundary in boundaries:
        ids = np.asarray(boundary['cells'], int)
        series = np.asarray(boundary['series'], float)
        if len(ids) != len(set(ids)) or any(int(i) in used for i in ids) or np.any(ids < 0) or np.any(ids >= n):
            raise ValueError('Boundary cells must be valid and disjoint')
        used.update(map(int, ids))
        if series.ndim != 2 or series.shape[1] != 2 or not np.isfinite(series).all() or np.any(np.diff(series[:, 0]) <= 0) or series[0, 0] > 0 or series[-1, 0] < duration:
            raise ValueError('Stage series must cover run with increasing times')
        if not np.isfinite(boundary.get('tracer_concentration', 0)) or boundary.get('tracer_concentration', 0) < 0: raise ValueError('Invalid boundary tracer')
    initial = float(v.sum()); initial_mass = float(mass.sum())
    external = 0.; tracer_external = 0.; rain_total = 0.; infil_total = 0.; gw_total = 0.; stage_total = 0.
    q = np.zeros(nf); frames = []; nextout = 0.; t = 0.; steps = 0
    maxdepth = np.zeros(n); exposure = np.zeros(n); ever = np.zeros(nf, bool); limiter_steps = 0
    integrated = np.zeros(nf); lastout = 0.
    def concentration():
        return np.divide(mass, v, out=np.zeros_like(v), where=v > 1e-12)
    def enforce(time):
        nonlocal external, tracer_external, stage_total
        for boundary in boundaries:
            ids = np.asarray(boundary['cells'], int); series = np.asarray(boundary['series'])
            level = np.interp(time, series[:, 0], series[:, 1])
            target = storage(np.full(len(ids), level), z[ids], area)
            delta = target - v[ids]
            cm = concentration()[ids]
            dm = np.where(delta >= 0, delta * boundary.get('tracer_concentration', 0.), delta * cm)
            mass[ids] += dm; v[ids] = target
            external += float(delta.sum()); stage_total += float(delta.sum()); tracer_external += float(dm.sum())
    enforce(0.)
    while True:
        eta = stage_from_volume(v, z, area)
        depth = v / area; maxdepth = np.maximum(maxdepth, depth)
        if t >= nextout - 1e-8 or t >= duration - 1e-8:
            af, widths, _ = face_geometry(eta[a], eta[b], profiles, dx / profiles.shape[1])
            frames.append({'time_s': t, 'depth_m': depth.tolist(), 'stage_m': eta.tolist(),
                'tracer_concentration': concentration().tolist(), 'flows_m3_s': q.tolist(),
                'active_width_m': widths.tolist(), 'preceding_interval_mean_flows_m3_s': (integrated / (t-lastout)).tolist() if t > lastout else q.tolist()})
            integrated[:] = 0; lastout = t; nextout += interval
        if t >= duration - 1e-8: break
        wetdepth = max(float(np.max(eta - z[:, 0])), 1e-3)
        dt = min(dtmax, cfl * dx / np.sqrt(G * wetdepth), duration - t, nextout - t)
        # Do not step across a prescribed hydrograph corner.
        for boundary in boundaries:
            future = [pt[0]-t for pt in boundary['series'] if pt[0] > t+1e-8]
            if future: dt = min(dt, min(future))
        af, widths, radius = face_geometry(eta[a], eta[b], profiles, dx / profiles.shape[1])
        valid = af > 1e-10
        trial = np.zeros(nf)
        trial[valid] = (q[valid] + G * af[valid] * dt * (eta[a[valid]]-eta[b[valid]]) / dx) / (1 + G*roughness**2*dt*np.abs(q[valid])/(af[valid]*np.maximum(radius[valid],1e-6)**(4/3)))
        donor = np.where(trial >= 0, a, b)
        outgoing = np.bincount(donor, weights=np.abs(trial)*dt, minlength=n)
        scale = np.minimum(1., np.divide(v, outgoing, out=np.ones(n), where=outgoing > 0))
        if np.any(scale < 1-1e-10): limiter_steps += 1
        q = trial * scale[donor]
        transfer = dt*q; mt = transfer * concentration()[donor]
        dv = np.bincount(b, weights=transfer, minlength=n)-np.bincount(a, weights=transfer, minlength=n)
        dm = np.bincount(b, weights=mt, minlength=n)-np.bincount(a, weights=mt, minlength=n)
        v += dv; mass += dm
        # Boundary sources and losses are applied conservatively after face transfer.
        addition = rain*area*dt
        v += addition; rain_total += addition*n; external += addition*n
        wet_fraction = (stage_from_volume(v, z, area)[:, None] > z).mean(axis=1)
        loss = np.minimum(v, infil*area*wet_fraction*dt)
        removed = loss*concentration(); mass -= removed; v -= loss
        infil_total += float(loss.sum()); external -= float(loss.sum()); tracer_external -= float(removed.sum())
        if conductance:
            current = stage_from_volume(v, z, area)
            exchange = conductance*(head-current)*dt
            exchange = np.maximum(exchange, -v)
            dm = np.minimum(exchange, 0)*concentration()  # external groundwater carries zero tracer
            mass += dm; v += exchange
            gw_total += float(exchange.sum()); external += float(exchange.sum()); tracer_external += float(dm.sum())
        if np.min(v) < -1e-7 or np.min(mass) < -1e-7 or not np.isfinite(v).all(): raise ValueError('Invalid state')
        v = np.maximum(v, 0); mass = np.maximum(mass, 0)
        integrated += transfer; ever |= np.abs(q) > config.get('active_flow_threshold_m3_s', 1e-6)
        exposure += depth*dt
        t += dt; enforce(t); steps += 1
        if steps > config.get('max_steps', 200000): raise ValueError('Step limit exceeded')
    return {'frames': frames, 'steps': steps, 'limiter_steps': limiter_steps,
        'maximum_depth_m': maxdepth.tolist(), 'integrated_depth_m_s': exposure.tolist(), 'ever_active_faces': ever.tolist(),
        'budget': {'initial_volume_m3': initial, 'external_net_m3': external, 'final_volume_m3': float(v.sum()),
            'residual_m3': initial+external-float(v.sum()), 'rainfall_m3': rain_total, 'infiltration_loss_m3': infil_total,
            'groundwater_net_m3': gw_total, 'stage_boundary_net_m3': stage_total},
        'tracer_budget': {'initial_mass': initial_mass, 'external_net_mass': tracer_external, 'final_mass': float(mass.sum()),
            'residual': initial_mass+tracer_external-float(mass.sum())}}
