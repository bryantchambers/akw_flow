"""One-way interval coupling of saved hydraulics to the transport mass ledger.

Storage evolves linearly within each saved hydraulic interval using its mean
signed flows. This retains water balance but cannot recover sub-interval flow
reversals or fluctuations absent from the saved output.
"""
import copy
import numpy as np
from .core import simulate


def simulate_coupled(config):
    config = copy.deepcopy(config)
    hydraulic = config.pop('hydraulic_result')
    nodes, edges, samples = (hydraulic[k] for k in ('nodes', 'edges', 'samples'))
    ids = [node['id'] for node in nodes]
    if not nodes or len(nodes) > 500 or len(set(ids)) != len(ids):
        raise ValueError('Coupling requires 1..500 uniquely identified nodes')
    if hydraulic['node_ids'] != ids or hydraulic['edge_ids'] != [e['id'] for e in edges]:
        raise ValueError('Hydraulic node/edge ordering does not match samples')
    if len(samples) < 2:
        raise ValueError('Coupling needs at least two hydraulic samples')
    n, lookup = len(nodes), {key: i for i, key in enumerate(ids)}

    def vector(value, size, name):
        a = np.asarray(value, float)
        if a.shape != (size,) or not np.isfinite(a).all():
            raise ValueError(f'{name} must have {size} finite entries')
        return a

    source = vector(hydraulic['external_flows_m3_s'], n, 'external flows')
    incoming = np.broadcast_to(np.asarray(config.get('boundary_concentration', 0), float), (n,))
    if not np.isfinite(incoming).all() or (incoming < 0).any():
        raise ValueError('Boundary concentrations must be finite and nonnegative')
    times = np.asarray([sample['time_s'] for sample in samples], float)
    if not np.isfinite(times).all() or times[0] != 0 or (np.diff(times) <= 0).any():
        raise ValueError('Hydraulic times must start at zero and increase strictly')
    storage = [vector(s['volumes_m3'], n, 'storage') for s in samples]
    if any((v <= 0).any() for v in storage):
        raise ValueError('Dry hydraulic storage is unsupported by coupled transport')
    base = {k: v for k, v in config.items() if k not in (
        'cells', 'connections', 'boundaries', 'boundary_concentration', 'edge_transport',
        'duration_s', 'output_interval_s', 'dynamic_volumes')}
    base['dynamic_volumes'] = True
    steps, snapshots, ledger, water_intervals = 0, [], None, []
    max_steps = int(config.get('max_steps', 100000))
    if not 1 <= max_steps <= 1000000:
        raise ValueError('max_steps must be 1..1000000')
    state = None
    for index, (start, end) in enumerate(zip(samples, samples[1:])):
        dt = float(times[index + 1] - times[index])
        flows = vector(end['preceding_interval_mean_flows_m3_s'], len(edges), 'interval mean flows')
        balance = source.copy()
        connections = []
        for edge, q in zip(edges, flows):
            a, b = lookup[edge['from']], lookup[edge['to']]
            balance[a] -= q
            balance[b] += q
            extra = config.get('edge_transport', {}).get(edge['id'], {})
            connections.append({**extra, 'from': edge['from'], 'to': edge['to'],
                                'flow_m3_s': float(q)})
        expected = storage[index] + dt * balance
        residual = storage[index + 1] - expected
        if not np.allclose(storage[index + 1], expected, rtol=1e-8, atol=1e-9):
            raise ValueError(f'Hydraulic interval {index} violates per-cell water balance')
        c = copy.deepcopy(base)
        c['max_steps'] = max_steps - steps
        if c['max_steps'] <= 0:
            raise ValueError('Coupled step limit exceeded')
        c['duration_s'] = dt
        c['output_interval_s'] = dt
        c['cells'] = [dict(id=node['id'], volume_m3=float(storage[index][i]),
                           bed_area_m2=node['storage_area_m2'],
                           **({'geometry': {'type': 'Point', 'coordinates': node['coordinates']}}
                              if 'coordinates' in node else {})) for i, node in enumerate(nodes)]
        c['connections'] = connections
        c['boundaries'] = [dict(cell=ids[i], flow_m3_s=float(q), concentration=float(incoming[i]))
                           for i, q in enumerate(source) if q != 0]
        if state is not None:
            # Preserve inventory even across the tiny storage roundoff at interval joins.
            c['initial_concentration'] = (np.asarray(state['water_mass']) / storage[index]).tolist()
            c['initial_bed_mass'] = state['bed_mass']
        state = simulate(c)
        if not np.allclose(state['volumes_m3'], storage[index + 1], rtol=1e-8, atol=1e-9):
            raise ValueError('Transport storage diverged from hydraulic storage')
        for snapshot in state['snapshots'][0 if index == 0 else 1:]:
            snapshot['time_s'] += float(times[index])
            snapshots.append(snapshot)
        budget = state['mass_budget']
        if ledger is None:
            ledger = {key: value for key, value in budget.items() if key not in ('final', 'residual')}
        else:
            for key in budget:
                if key not in ('initial', 'final', 'residual'):
                    ledger[key] += budget[key]
        steps += state['steps']
        water_intervals.append({'start_s': float(times[index]), 'end_s': float(times[index + 1]),
                                'max_cell_residual_m3': float(abs(residual).max())})
    ledger['final'] = state['mass_budget']['final']
    ledger['residual'] = ledger['final'] - (ledger['initial'] + ledger['boundary_input'] +
        ledger['local_input'] + ledger['production_or_atmospheric_input'] -
        ledger['boundary_export'] - ledger['irreversible_loss_or_export'])
    state.update(time_s=float(times[-1]), steps=steps, snapshots=snapshots, mass_budget=ledger)
    state['water_budget'] = dict(initial_volume_m3=float(storage[0].sum()),
        final_volume_m3=float(storage[-1].sum()), external_net_m3=float(source.sum() * times[-1]),
        residual_m3=float(storage[-1].sum() - storage[0].sum() - source.sum() * times[-1]),
        intervals=water_intervals)
    state['coupling'] = {'method': 'preceding_interval_mean_flows_m3_s with evolving storage',
                         'hydraulic_intervals': len(samples) - 1}
    state['warnings'] = ['Exploratory uncalibrated terrain network; no historical prediction.',
        'Interval means preserve water balance but omit unresolved flow reversals and fluctuations.',
        'Conservative defaults have no organism-specific or chemical reaction calibration.']
    for feature in state['geojson']['features']:
        feature['properties']['time_s'] = float(times[-1])
    return state
