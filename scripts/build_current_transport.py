#!/usr/bin/env python3
"""Reuse saved hydraulics to write conservative biological/chemical demonstrations."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transport.core import MODULES, simulate

ROOT = Path(__file__).resolve().parents[1]


def build():
    source = ROOT / 'assets/data/hydraulics/simulation.json'
    hydraulic = json.loads(source.read_text())
    initial = [0.] * len(hydraulic['nodes'])
    # Arbitrary unit tracer in a connected cell; no measured contamination implied.
    initial[hydraulic['node_ids'].index(hydraulic['edges'][0]['from'])] = 1.
    output = ROOT / 'assets/data/transport'
    output.mkdir(exist_ok=True)
    manifest = {'status': 'Uncalibrated conservative demonstrations; no fitted reaction rates',
                'hydraulic_source': str(source.relative_to(ROOT)),
                'hydraulic_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'initial_condition': 'Arbitrary unit tracer in the first edge source cell',
                'results': {}}
    for model, module in MODULES.items():
        config = dict(model=model, hydraulic_result=hydraulic,
                      scenario='Saved terrain-candidate hydraulics; arbitrary conservative tracer',
                      initial_concentration=initial, initial_bed_mass=0,
                      boundary_concentration=0, dt_max_s=.05,
                      parameters=module.default_parameters(), environment={})
        result = simulate(config)
        for name, data in ((f'current_{model}_config.json', config),
                           (f'current_{model}_result.json', result),
                           (f'current_{model}_output.geojson', result['geojson'])):
            (output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
        manifest['results'][model] = dict(mass_budget=result['mass_budget'],
            water_budget=result['water_budget'], steps=result['steps'], time_s=result['time_s'])
        if model == 'chemical':
            (ROOT / 'assets/data/hydraulics/transport_config.json').write_text(
                json.dumps(config, indent=2, allow_nan=False) + '\n')
    (output / 'current_manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    build()
