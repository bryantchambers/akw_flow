"""Conservative finite-volume transport on prescribed, water-balanced networks."""
import copy
import numpy as np
from . import biology, chemistry

MODULES = {'biological': biology, 'chemical': chemistry}


def get_models():
    return {name: {'parameters': module.parameter_definitions(),
                   'defaults': module.default_parameters(), 'presets': module.load_presets()}
            for name, module in MODULES.items()}


def _number(value, name, minimum=None):
    value = float(value)
    if not np.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f'{name} must be finite and >= {minimum}')
    return value


def simulate(config):
    """Integrate fixed-volume control cells using upwind advection and Fickian exchange.

    Flow units m3/s, length m, area m2, dispersion m2/s, concentrations viable
    counts/m3 (biological) or mg/m3 (chemical). Boundary flows positive inward.
    This routine does not solve hydraulics. Zero-volume junctions are unsupported.
    """
    if 'hydraulic_result' in config:
        from .coupling import simulate_coupled
        return simulate_coupled(config)
    config = copy.deepcopy(config)
    model = config.get('model', 'chemical')
    if model not in MODULES:
        raise ValueError('model must be biological or chemical')
    module = MODULES[model]
    cells = config['cells']
    if not cells or len(cells) > 10000:
        raise ValueError('Require 1..10000 cells')
    ids = [c['id'] for c in cells]
    if len(set(ids)) != len(ids):
        raise ValueError('Cell IDs must be unique')
    lookup = {identifier: i for i, identifier in enumerate(ids)}
    n = len(cells)
    def array(value, name):
        a = np.broadcast_to(np.asarray(value, float), (n,)).copy()
        if np.any(~np.isfinite(a)) or np.any(a < 0):
            raise ValueError(f'{name} must be finite and nonnegative')
        return a
    volumes = array([c['volume_m3'] for c in cells], 'volume')
    if np.any(volumes <= 0):
        raise ValueError('Cell volumes must be positive')
    areas = array([c.get('bed_area_m2', 0) for c in cells], 'bed area')
    water = array(config.get('initial_concentration', 0), 'initial concentration') * volumes
    bed = array(config.get('initial_bed_mass', 0), 'initial bed mass')
    loads = array(config.get('loading_per_s', 0), 'loading_per_s')
    edges, boundaries = [], []
    balance, throughput = np.zeros(n), np.zeros(n)
    for edge in config.get('connections', []):
        i, j = lookup[edge['from']], lookup[edge['to']]
        if i == j:
            raise ValueError('Self edges are unsupported')
        q = _number(edge['flow_m3_s'], 'flow')
        d = sum(_number(edge.get(k, 0), k, 0) for k in ('dispersion_m2_s', 'molecular_diffusion_m2_s'))
        conductance = 0.0
        if d:
            distance = _number(edge['distance_m'], 'distance_m', 0)
            if distance == 0:
                raise ValueError('Diffusive distance must be positive')
            conductance = d * _number(edge['area_m2'], 'area_m2', 0) / distance
        balance[i] -= q
        balance[j] += q
        throughput[i] += max(q, 0) + conductance
        throughput[j] += max(-q, 0) + conductance
        edges.append((i, j, q, conductance))
    for boundary in config.get('boundaries', []):
        i = lookup[boundary['cell']]
        q = _number(boundary['flow_m3_s'], 'boundary flow')
        concentration = _number(boundary.get('concentration', 0), 'boundary concentration', 0)
        balance[i] += q
        throughput[i] += max(-q, 0)
        boundaries.append((i, q, concentration))
    tolerance = 1e-10 * np.maximum(1, throughput)
    dynamic = config.get('dynamic_volumes', False)
    if not isinstance(dynamic, bool):
        raise ValueError('dynamic_volumes must be boolean')
    if not dynamic and np.any(abs(balance) > tolerance):
        raise ValueError('Fixed-volume hydraulics violate per-cell water balance; supply balanced boundary flows')
    duration = _number(config.get('duration_s', 3600), 'duration_s', 0)
    dt_max = _number(config.get('dt_max_s', 10), 'dt_max_s', 0)
    if dt_max <= 0:
        raise ValueError('dt_max_s must be positive')
    max_steps = int(config.get('max_steps', 100000))
    if not 1 <= max_steps <= 1000000:
        raise ValueError('max_steps must be 1..1000000')
    parameters = config.get('parameters', {})
    if config.get('preset'):
        defaults = module.get_preset(config['preset'])['parameters']
        defaults.update(parameters)
        parameters = defaults
    environment = config.get('environment', {})
    initial = float(water.sum() + bed.sum())
    ledger = dict(boundary_input=0., local_input=0., production_or_atmospheric_input=0.,
                  boundary_export=0., irreversible_loss_or_export=0.)
    snapshots = []
    interval = _number(config.get('output_interval_s', max(duration / 20, dt_max)), 'output interval', 0)
    if interval <= 0:
        raise ValueError('output_interval_s must be positive')
    t, step, next_output = 0., 0, interval
    def snapshot():
        return {'time_s': t, 'concentration': (water / volumes).tolist(), 'bed_mass': bed.tolist(), 'volumes_m3': volumes.tolist()}
    snapshots.append(snapshot())
    while t < duration:
        if step >= max_steps:
            raise ValueError('Step limit exceeded; inspect stiffness and increase max_steps explicitly')
        concentration = water / volumes
        r = module.reaction_tendencies(water, bed, volumes, areas, parameters, environment)
        dw = np.asarray(r['water'], float).copy() + loads
        db = np.asarray(r['bed'], float).copy()
        losses = np.asarray(r['irreversible_loss'], float)
        production = np.asarray(r.get('external_source', r.get('atmospheric_input', np.zeros(n))), float)
        if np.any(losses < 0) or np.any(production < 0) or not np.allclose(r['water'] + r['bed'], production - losses, rtol=1e-9, atol=1e-10):
            raise ValueError('Reaction module violates compartment ledger')
        for i, j, q, conductance in edges:
            flux = q * (concentration[i] if q >= 0 else concentration[j]) + conductance * (concentration[i] - concentration[j])
            dw[i] -= flux
            dw[j] += flux
        inlet = outlet = 0.
        for i, q, cin in boundaries:
            if q >= 0:
                incoming = q * cin
                dw[i] += incoming
                inlet += incoming
            else:
                outgoing = -q * concentration[i]
                dw[i] -= outgoing
                outlet += outgoing
        dt = min(dt_max, duration - t, max(next_output - t, 1e-12))
        active = throughput > 0
        if np.any(active):
            dt = min(dt, float(np.min(0.5 * volumes[active] / throughput[active])))
        for mass, rate in ((water, dw), (bed, db), (volumes, balance if dynamic else np.zeros(n))):
            if np.any(~np.isfinite(rate)):
                raise ValueError('Nonfinite tendency')
            draining = rate < 0
            if np.any(draining):
                dt = min(dt, float(np.min(0.2 * mass[draining] / -rate[draining])))
        if dt <= 0 or t + dt == t:
            raise ValueError('Cannot advance positive state; inspect rates or stiffness')
        water += dt * dw
        bed += dt * db
        if dynamic:
            volumes += dt * balance
        if np.any(water < 0) or np.any(bed < 0):
            raise ValueError('Positivity failure')
        ledger['boundary_input'] += dt * inlet
        ledger['boundary_export'] += dt * outlet
        ledger['local_input'] += dt * float(loads.sum())
        ledger['production_or_atmospheric_input'] += dt * float(production.sum())
        ledger['irreversible_loss_or_export'] += dt * float(losses.sum())
        t += dt
        step += 1
        if t >= next_output - 1e-9 or t >= duration:
            snapshots.append(snapshot())
            next_output += interval
    final = float(water.sum() + bed.sum())
    expected = initial + ledger['boundary_input'] + ledger['local_input'] + ledger['production_or_atmospheric_input'] - ledger['boundary_export'] - ledger['irreversible_loss_or_export']
    unit = 'viable-count/m3' if model == 'biological' else 'mg/m3'
    features = []
    for i, cell in enumerate(cells):
        if cell.get('geometry'):
            features.append({'type': 'Feature', 'geometry': cell['geometry'], 'properties': {
                'id': cell['id'], 'value': float(water[i] / volumes[i]), 'bed_mass': float(bed[i]),
                'time_s': t, 'status': 'unvalidated prescribed-flow simulation'}})
    return {'model': model, 'steps': step, 'time_s': t, 'cell_ids': ids,
            'concentration_unit': unit, 'concentration': (water / volumes).tolist(),
            'water_mass': water.tolist(), 'bed_mass': bed.tolist(), 'volumes_m3': volumes.tolist(), 'snapshots': snapshots,
            'mass_budget': dict(ledger, initial=initial, final=final, residual=final - expected),
            'geojson': {'type': 'FeatureCollection', 'model': {
                'name': 'Finite-volume ' + model + ' transport', 'scenario': config.get('scenario', 'Uncalibrated scenario'),
                'metric': 'Water concentration', 'unit': unit}, 'features': features}}
