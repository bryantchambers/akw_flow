"""Configurable viable microbial inventories; SI units, no universal fitted rates.

RHS only: caller integrates with a positivity-preserving timestep. All enabled
processes require explicit coefficients. Presets supply identity/evidence, not
uncalibrated environmental decay rates. See docs/biological_model.md.
"""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np

_FLAGS = ['dark', 'solar', 'uv', 'settling', 'attachment', 'detachment', 'resuspension', 'growth']
PARAMETER_DEFINITIONS = {
    'dark_water_s': ('s^-1', 'Water reference-temperature viable loss; includes death, predation and dark inactivation only once.'),
    'dark_bed_s': ('s^-1', 'Bed reference-temperature viable loss.'),
    'q10': ('1', 'Optional dark-rate multiplier per 10 degrees C; null means no temperature scaling.'),
    'reference_temperature_c': ('degC', 'Reference temperature for dark loss.'),
    'temperature_min_c': ('degC', 'Lower calibrated temperature bound; outside range raises an error.'),
    'temperature_max_c': ('degC', 'Upper calibrated temperature bound; outside range raises an error.'),
    'solar_coefficient_m2_j': ('m^2/J', 'Natural-sunlight loss per matched biologically effective radiant exposure, not lamp UV coefficient.'),
    'light_attenuation_m': ('m^-1', 'Effective spectral attenuation for solar exposure.'),
    'solar_shielded_fraction': ('1', 'Fraction completely shielded from solar exposure, range 0..1.'),
    'uv_coefficient_m2_j': ('m^2/J', 'User-calibrated engineered-UV natural-log viable-loss response per fluence.'),
    'settling_velocity_m_s': ('m/s', 'Particle-associated effective deposition velocity.'),
    'particle_associated_fraction': ('1', 'Settling-eligible water inventory fraction, range 0..1.'),
    'attachment_s': ('s^-1', 'Direct water-to-bed attachment; independent of settling.'),
    'detachment_s': ('s^-1', 'Bed-to-water detachment.'),
    'resuspension_s': ('s^-1', 'Bed mobilization coefficient above critical shear.'),
    'critical_shear_pa': ('Pa', 'Resuspension threshold.'),
    'growth_s': ('s^-1', 'Maximum specific growth rate, water only.'),
    'carrying_capacity_count_m3': ('viable-count/m^3', 'Positive logistic carrying capacity.'),
}
_DEFAULTS = {key: None for key in PARAMETER_DEFINITIONS}
_DEFAULTS.update({f'{flag}_enabled': False for flag in _FLAGS})
_DEFAULTS.update(growth_permitted=False)


def default_parameters():
    return deepcopy(_DEFAULTS)


def parameter_definitions():
    result = {k: {'units': v[0], 'description': v[1], 'default': _DEFAULTS[k]} for k, v in PARAMETER_DEFINITIONS.items()}
    result.update({f'{f}_enabled': {'units': 'boolean', 'default': False} for f in _FLAGS})
    result['growth_permitted'] = {'units': 'boolean', 'default': False, 'description': 'Explicit organism/stage eligibility; dormant spores and protozoan cysts/oocysts must remain false.'}
    return result


def load_presets():
    return json.loads(Path(__file__).with_name('data').joinpath('biological_presets.json').read_text())


def get_preset(preset_id):
    for preset in load_presets()['presets']:
        if preset_id == preset['id'] or preset_id in preset.get('aliases', []):
            result = deepcopy(preset)
            result['parameters'] = {**default_parameters(), **result.get('parameters', {})}
            return result
    raise ValueError(f'Unknown biological preset: {preset_id}')


def validate_parameters(parameters):
    unknown = set(parameters) - set(_DEFAULTS)
    if unknown:
        raise ValueError(f'Unknown biological parameters: {sorted(unknown)}')
    p = {**default_parameters(), **parameters}
    for key, value in p.items():
        if key.endswith('_enabled') or key == 'growth_permitted':
            if not isinstance(value, (bool, np.bool_)):
                raise ValueError(f'{key} must be boolean')
        elif value is not None:
            try:
                a = np.asarray(value, dtype=float)
            except (TypeError, ValueError) as error:
                raise ValueError(f'{key} must be numeric') from error
            if not np.all(np.isfinite(a)) or (key not in ('reference_temperature_c', 'temperature_min_c', 'temperature_max_c') and np.any(a < 0)):
                raise ValueError(f'{key} must be finite and nonnegative (temperatures may be signed)')
    for key in ('particle_associated_fraction', 'solar_shielded_fraction'):
        if p[key] is not None and np.any(np.asarray(p[key]) > 1):
            raise ValueError(f'{key} must be in [0, 1]')
    required = {
        'dark': ['dark_water_s', 'dark_bed_s'],
        'solar': ['solar_coefficient_m2_j', 'light_attenuation_m', 'solar_shielded_fraction'],
        'uv': ['uv_coefficient_m2_j'],
        'settling': ['settling_velocity_m_s', 'particle_associated_fraction'],
        'attachment': ['attachment_s'], 'detachment': ['detachment_s'],
        'resuspension': ['resuspension_s', 'critical_shear_pa'],
        'growth': ['growth_s', 'carrying_capacity_count_m3'],
    }
    for process, keys in required.items():
        if p[process + '_enabled'] and any(p[k] is None for k in keys):
            raise ValueError(f'{process} enabled but coefficients missing: {keys}')
    if p['q10'] is not None:
        if np.any(np.asarray(p['q10']) <= 0) or any(p[k] is None for k in ('reference_temperature_c', 'temperature_min_c', 'temperature_max_c')):
            raise ValueError('q10 requires positive q10, reference temperature and calibrated bounds')
        if np.any(np.asarray(p['temperature_min_c']) > np.asarray(p['temperature_max_c'])):
            raise ValueError('temperature bounds reversed')
        if np.any(np.asarray(p['reference_temperature_c']) < np.asarray(p['temperature_min_c'])) or np.any(np.asarray(p['reference_temperature_c']) > np.asarray(p['temperature_max_c'])):
            raise ValueError('reference temperature must be within calibrated bounds')
    if p['growth_enabled'] and (not p['growth_permitted'] or np.any(np.asarray(p['carrying_capacity_count_m3']) <= 0)):
        raise ValueError('growth requires organism eligibility and positive carrying capacity')
    return p


def reaction_tendencies(water_mass, bed_mass, water_volume_m3, bed_area_m2, parameters, environment):
    """Return compartment rates in viable-count/s; parameters may be scalar/arrays.

    Required environmental fields only when their process is active:
    temperature_c (Q10), solar_irradiance_w_m2/depth_m (solar),
    uv_fluence_rate_w_m2 (UV), bed_shear_pa (resuspension). Solar irradiance
    must match the calibrated coefficient spectrum, not arbitrary broadband light.
    """
    p = validate_parameters(parameters)
    w, b, v, area = np.broadcast_arrays(*[np.asarray(x, dtype=float) for x in (water_mass, bed_mass, water_volume_m3, bed_area_m2)])
    for key, a in [('water_mass', w), ('bed_mass', b), ('water_volume_m3', v), ('bed_area_m2', area)]:
        if not np.all(np.isfinite(a)) or np.any(a < 0) or (key == 'water_volume_m3' and np.any(a <= 0)):
            raise ValueError(f'{key} must be finite and nonnegative; volume must be positive')
    def field(key, signed=False):
        if key not in environment:
            raise ValueError(f'Missing environmental field: {key}')
        a = np.broadcast_to(np.asarray(environment[key], dtype=float), w.shape)
        if not np.all(np.isfinite(a)) or (not signed and np.any(a < 0)):
            raise ValueError(f'Invalid environmental field: {key}')
        return a
    def coefficient(key):
        return np.broadcast_to(np.asarray(p[key], dtype=float), w.shape)
    zero = np.zeros_like(w)
    dw, db = zero.copy(), zero.copy()
    out = {}
    kw, kb = zero.copy(), zero.copy()
    if p['dark_enabled']:
        factor = np.ones_like(w)
        if p['q10'] is not None:
            t = field('temperature_c', signed=True)
            if np.any(t < coefficient('temperature_min_c')) or np.any(t > coefficient('temperature_max_c')):
                raise ValueError('temperature_c outside calibrated Q10 range')
            factor = coefficient('q10') ** ((t - coefficient('reference_temperature_c')) / 10)
        kw += coefficient('dark_water_s') * factor
        kb += coefficient('dark_bed_s') * factor
    out['dark_water_loss'] = kw * w
    out['dark_bed_loss'] = kb * b
    for process in ('solar', 'uv'):
        k = zero.copy()
        if p[process + '_enabled']:
            if process == 'solar':
                x = coefficient('light_attenuation_m') * field('depth_m')
                transmission = np.ones_like(x)
                np.divide(-np.expm1(-x), x, out=transmission, where=x != 0)
                k = coefficient('solar_coefficient_m2_j') * field('solar_irradiance_w_m2') * transmission * (1 - coefficient('solar_shielded_fraction'))
            else:
                k = coefficient('uv_coefficient_m2_j') * field('uv_fluence_rate_w_m2')
        out[process + '_water_loss'] = k * w
        kw += k
    for process in ('settling', 'attachment', 'detachment', 'resuspension'):
        k = zero.copy()
        if p[process + '_enabled']:
            if process == 'settling':
                k = coefficient('settling_velocity_m_s') * coefficient('particle_associated_fraction') * area / v
            elif process == 'resuspension':
                # Threshold-activated first-order bed mobilization.
                k = coefficient('resuspension_s') * (field('bed_shear_pa') > coefficient('critical_shear_pa'))
            else:
                k = coefficient(process + '_s')
        rate = k * (w if process in ('settling', 'attachment') else b)
        out[process + '_transfer'] = rate
        sign = -1 if process in ('settling', 'attachment') else 1
        dw += sign * rate
        db -= sign * rate
        if sign == -1:
            kw += k
        else:
            kb += k
    growth = zero.copy()
    if p['growth_enabled']:
        growth = coefficient('growth_s') * w * np.maximum(0, 1 - w / v / coefficient('carrying_capacity_count_m3'))
    loss_w = out['dark_water_loss'] + out['solar_water_loss'] + out['uv_water_loss']
    loss_b = out['dark_bed_loss']
    out.update(water=dw + growth - loss_w, bed=db - loss_b,
               irreversible_loss=loss_w + loss_b, growth_production=growth, external_source=growth,
               water_outgoing_rate_s=kw, bed_outgoing_rate_s=kb)
    return out
