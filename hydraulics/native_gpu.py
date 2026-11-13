"""CUDA native-grid local-inertial solver; same four conservative phases as CPU.

All hydraulic fields remain resident on one GPU. Only seven reduced diagnostics
are read per timestep. CUDA is optional and imported by the backend dispatcher
only when the maintained numba-cuda provider and a visible device are present.
"""
import math
import time
import numpy as np
from numba import cuda, float64

G = 9.80665
TPB = 256


@cuda.jit(cache=True, fastmath=False)
def zero_flux(qx, qy):
    k = cuda.grid(1)
    if k < qx.size:
        qx[k] = 0.0
        qy[k] = 0.0


@cuda.jit(cache=True, fastmath=False)
def momentum(z, h, qx, qy, cols, dt, dx, n, dry):
    k = cuda.grid(1)
    if k >= z.size:
        return
    za = z[k]
    if not math.isfinite(za):
        qx[k] = 0.0
        qy[k] = 0.0
        return
    eta = za + h[k]
    if k % cols + 1 < cols and math.isfinite(z[k + 1]):
        zb = z[k + 1]
        eb = zb + h[k + 1]
        d = max(eta, eb) - max(za, zb)
        if d > dry and (eta != eb or qx[k] != 0):
            predictor = qx[k] + G * d * dt * (eta - eb) / dx
            alpha = G * n * n * dt / d ** (7.0 / 3.0)
            qx[k] = 2 * predictor / (1 + math.sqrt(1 + 4 * alpha * abs(predictor)))
        else:
            qx[k] = 0.0
    else:
        qx[k] = 0.0
    if k + cols < z.size and math.isfinite(z[k + cols]):
        zb = z[k + cols]
        eb = zb + h[k + cols]
        d = max(eta, eb) - max(za, zb)
        if d > dry and (eta != eb or qy[k] != 0):
            predictor = qy[k] + G * d * dt * (eta - eb) / dx
            alpha = G * n * n * dt / d ** (7.0 / 3.0)
            qy[k] = 2 * predictor / (1 + math.sqrt(1 + 4 * alpha * abs(predictor)))
        else:
            qy[k] = 0.0
    else:
        qy[k] = 0.0


@cuda.jit(cache=True, fastmath=False)
def donor_scales(h, qx, qy, scale, cols, dt, dx):
    k = cuda.grid(1)
    if k >= h.size:
        return
    out = max(0.0, qx[k]) + max(0.0, qy[k])
    if k % cols:
        out += max(0.0, -qx[k - 1])
    if k >= cols:
        out += max(0.0, -qy[k - cols])
    scale[k] = min(1.0, h[k] * dx / (dt * out)) if out > 0 else 1.0


@cuda.jit(cache=True, fastmath=False)
def limit_faces(qx, qy, scale, cols):
    k = cuda.grid(1)
    if k >= scale.size:
        return
    if k % cols + 1 < cols:
        qx[k] *= scale[k] if qx[k] >= 0 else scale[k + 1]
    if k + cols < scale.size:
        qy[k] *= scale[k] if qy[k] >= 0 else scale[k + cols]


@cuda.jit(device=True, inline=True)
def concentration(m, h):
    return m / h if h > 1e-12 else 0.0


@cuda.jit(cache=True, fastmath=False)
def update(z, h, m, qx, qy, hn, mn, cols, dt, dx, rain, infil, partials):
    k = cuda.grid(1)
    t = cuda.threadIdx.x
    block = cuda.blockIdx.x
    values = cuda.shared.array((7, TPB), float64)
    for j in range(7):
        values[j, t] = 0.0
    if k < h.size:
        if not math.isfinite(z[k]):
            hn[k] = 0.0
            mn[k] = 0.0
        else:
            hc = h[k]
            mc = m[k]
            cc = concentration(mc, hc)
            right = qx[k]
            south = qy[k]
            left = qx[k - 1] if k % cols else 0.0
            north = qy[k - cols] if k >= cols else 0.0
            mr = right * (cc if right >= 0 or k % cols + 1 == cols else concentration(m[k + 1], h[k + 1]))
            ms = south * (cc if south >= 0 or k + cols >= h.size else concentration(m[k + cols], h[k + cols]))
            ml = left * (concentration(m[k - 1], h[k - 1]) if left >= 0 and k % cols else cc)
            mt = north * (concentration(m[k - cols], h[k - cols]) if north >= 0 and k >= cols else cc)
            hh = max(0.0, hc + dt / dx * (left + north - right - south) + rain * dt)
            mm = max(0.0, mc + dt / dx * (ml + mt - mr - ms))
            loss = min(hh, infil * dt) if hh > 0 else 0.0
            removed = loss * concentration(mm, hh)
            hh -= loss
            mm -= removed
            hn[k] = hh
            mn[k] = mm
            values[0, t] = hh
            values[1, t] = mm
            values[2, t] = loss
            values[3, t] = removed
            values[4, t] = hh
            if hh > 1e-4:
                values[5, t] = max(abs(left), abs(right), abs(north), abs(south)) / hh
            if hh > 1e-3:
                values[6, t] = 1.0
    cuda.syncthreads()
    stride = TPB // 2
    while stride:
        if t < stride:
            for j in range(7):
                if j == 4 or j == 5:
                    values[j, t] = max(values[j, t], values[j, t + stride])
                else:
                    values[j, t] += values[j, t + stride]
        cuda.syncthreads()
        stride //= 2
    if t == 0:
        for j in range(7):
            partials[j, block] = values[j, 0]


@cuda.jit(cache=True, fastmath=False)
def reduce_diagnostics(source, target):
    k = cuda.grid(1)
    t = cuda.threadIdx.x
    block = cuda.blockIdx.x
    values = cuda.shared.array((7, TPB), float64)
    for j in range(7):
        values[j, t] = source[j, k] if k < source.shape[1] else 0.0
    cuda.syncthreads()
    stride = TPB // 2
    while stride:
        if t < stride:
            for j in range(7):
                if j == 4 or j == 5:
                    values[j, t] = max(values[j, t], values[j, t + stride])
                else:
                    values[j, t] += values[j, t + stride]
        cuda.syncthreads()
        stride //= 2
    if t == 0:
        for j in range(7):
            target[j, block] = values[j, 0]


def simulate(z, initial_depth, config, initial_concentration=None, callback=None):
    started = time.monotonic()
    from .native_grid import parameters
    p = parameters(config)
    if z.ndim != 2 or z.shape != initial_depth.shape:
        raise ValueError('Matching 2D terrain/depth required')
    z = np.ascontiguousarray(z, dtype=np.float32)
    h = np.asarray(initial_depth, dtype=np.float64).copy(order='C')
    if not np.isfinite(h).all() or np.any(h < 0):
        raise ValueError('Finite nonnegative initial depth required')
    valid = np.isfinite(z)
    h[~valid] = 0
    validcount = int(valid.sum())
    del valid
    if initial_concentration is None:
        m = np.zeros_like(h)
    else:
        c = np.asarray(initial_concentration)
        if c.shape != h.shape or not np.isfinite(c).all() or np.any(c < 0):
            raise ValueError('Invalid tracer concentration')
        m = h * c
    shape = z.shape
    cols = shape[1]
    size = z.size
    if size == 0:
        raise ValueError('Nonempty terrain required')
    dx = p['spacing_m']
    da = dx * dx
    initial = float(h.sum(dtype=np.float64) * da)
    initialmass = float(m.sum(dtype=np.float64) * da)
    maxh = float(h.max())
    device = cuda.get_current_device()
    free, total = cuda.current_context().get_memory_info()
    required = size * 60 + 2 * ((size + TPB - 1) // TPB) * 7 * 8
    if free < required * 1.05:
        raise MemoryError(f'GPU requires about {required / 2**30:.2f} GiB plus headroom; free {free / 2**30:.2f} GiB')
    dz = cuda.to_device(z.ravel())
    dh = cuda.to_device(h.ravel())
    dm = cuda.to_device(m.ravel())
    del h, m
    qx = cuda.device_array(size, np.float64)
    qy = cuda.device_array(size, np.float64)
    hn = cuda.device_array(size, np.float64)
    mn = cuda.device_array(size, np.float64)
    scale = cuda.device_array(size, np.float64)
    blocks = (size + TPB - 1) // TPB
    zero_flux[blocks, TPB](qx, qy)
    summaries = [cuda.device_array((7, blocks), np.float64)]
    while summaries[-1].shape[1] > 1:
        summaries.append(cuda.device_array((7, (summaries[-1].shape[1] + TPB - 1) // TPB), np.float64))
    cuda.synchronize()
    setup_s = time.monotonic() - started
    t = 0.0
    steps = 0
    rainnet = infilnet = massloss = 0.0
    history = []
    solve_start = time.monotonic()
    last_report = -1e30
    stats = None
    while t < p['duration_s'] - 1e-10:
        dt = min(p['dt_max_s'], p['duration_s'] - t, p['cfl'] * dx / np.sqrt(G * max(maxh, 1e-6)))
        if not np.isfinite(dt) or dt < 1e-8:
            raise ValueError('Native timestep collapsed; inspect geometry / forcing')
        momentum[blocks, TPB](dz, dh, qx, qy, cols, dt, dx, p['manning_n'], p['dry_depth_m'])
        donor_scales[blocks, TPB](dh, qx, qy, scale, cols, dt, dx)
        limit_faces[blocks, TPB](qx, qy, scale, cols)
        update[blocks, TPB](dz, dh, dm, qx, qy, hn, mn, cols, dt, dx, p['rainfall_mm_hr'] / 3.6e6, p['infiltration_mm_hr'] / 3.6e6, summaries[0])
        for source, target in zip(summaries, summaries[1:]):
            reduce_diagnostics[target.shape[1], TPB](source, target)
        stats = summaries[-1].copy_to_host()[:, 0]
        dh, hn = hn, dh
        dm, mn = mn, dm
        maxh = float(stats[4])
        rainnet += p['rainfall_mm_hr'] / 3.6e6 * dt * validcount * da
        infilnet += float(stats[2] * da)
        massloss += float(stats[3] * da)
        t += dt
        steps += 1
        if steps > int(config.get('max_steps', 200000)):
            raise ValueError('Native step limit reached')
        if time.monotonic() - last_report >= float(config.get('progress_interval_wall_s', 10)) or t >= p['duration_s'] - 1e-10:
            volume = float(stats[0] * da)
            mass = float(stats[1] * da)
            record = {'time_s': t, 'duration_s': p['duration_s'], 'steps': steps, 'dt_s': dt,
                      'maximum_depth_m': maxh, 'maximum_speed_proxy_m_s': float(stats[5]),
                      'wet_cells': int(stats[6]), 'water_volume_m3': volume, 'unit_tracer_mass': mass,
                      'water_residual_m3': initial + rainnet - infilnet - volume,
                      'tracer_residual': initialmass - massloss - mass,
                      'wall_s': time.monotonic() - solve_start, 'backend': 'gpu'}
            history.append(record)
            if callback:
                callback(record)
            last_report = time.monotonic()
    cuda.synchronize()
    solve_s = time.monotonic() - solve_start
    copy_start = time.monotonic()
    result = {'depth': dh.copy_to_host().reshape(shape), 'momentum_depth': hn.copy_to_host().reshape(shape),
              'face_depth_time_s': t - dt, 'mass_per_area': dm.copy_to_host().reshape(shape),
              'qx_per_width': qx.copy_to_host().reshape(shape), 'qy_per_width': qy.copy_to_host().reshape(shape),
              'history': history, 'steps': steps,
              'budget': {'initial_volume_m3': initial, 'rainfall_m3': rainnet, 'infiltration_loss_m3': infilnet,
                         'final_volume_m3': float(stats[0] * da), 'residual_m3': initial + rainnet - infilnet - float(stats[0] * da)},
              'tracer_budget': {'initial_mass': initialmass, 'infiltration_loss': massloss,
                               'final_mass': float(stats[1] * da), 'residual': initialmass - massloss - float(stats[1] * da)}}
    name = device.name.decode() if isinstance(device.name, bytes) else str(device.name)
    result['execution'] = {'backend': 'gpu', 'device': name, 'precision': 'float64 hydraulic state and donor scales; float32 terrain',
                           'setup_s': setup_s, 'solver_s': solve_s, 'download_s': time.monotonic() - copy_start,
                           'total_s': time.monotonic() - started, 'device_memory_estimate_bytes': required,
                           'device_memory_total_bytes': int(total), 'threads_per_block': TPB}
    # Explicitly release our allocations between sequential benchmark runs.
    del dz, dh, dm, qx, qy, hn, mn, scale, summaries
    cuda.current_context().deallocations.clear()
    return result
