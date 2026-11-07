"""Configurable one-chemical water/active-bed reaction rates (mg and seconds).

This is an environmental screening model, not an EPA WASP implementation.
Hydraulic routing and time integration belong to transport.core.
"""
import copy
import json
from pathlib import Path

import numpy as np


DEFAULT_PARAMETERS = {
    "biodegradation_enabled": False,
    "biodegradation_rate_s": None,
    "biodegradation_theta": 1.0,
    "hydrolysis_enabled": False,
    "hydrolysis_rate_s": None,
    "hydrolysis_theta": 1.0,
    "photolysis_enabled": False,
    "photolysis_rate_s": None,
    "photolysis_reference": "natural_sunlight",
    "volatilization_enabled": False,
    "mass_transfer_velocity_m_s": None,
    "equilibrium_water_concentration_mg_m3": 0.0,
    "sorption_enabled": False,
    "partition_mode": "kd",
    "kd_l_kg": None,
    "koc_l_kg_oc": None,
    "organic_carbon_fraction": None,
    "exchange_rate_s": None,
    "bed_dry_mass_kg_m2": None,
    "bed_degradation_enabled": False,
    "bed_degradation_rate_s": None,
    "bed_degradation_theta": 1.0,
    "reference_temperature_c": 20.0,
}

_DETAILS = {
    "biodegradation_rate_s": ("s^-1", "Condition-specific first-order dissolved parent biodegradation."),
    "hydrolysis_rate_s": ("s^-1", "Condition-specific hydrolysis of dissolved parent; no automatic pH law."),
    "photolysis_rate_s": ("s^-1", "Effective dissolved parent photolysis at the stated reference light field."),
    "mass_transfer_velocity_m_s": ("m/s", "Overall water-equivalent air/water transfer velocity; include two-film resistance externally."),
    "equilibrium_water_concentration_mg_m3": ("mg/m^3", "Water concentration in equilibrium with ambient air; zero is clean-air assumption."),
    "kd_l_kg": ("L/kg dry sediment", "Linear dissolved-water/bed partition coefficient; converted to m^3/kg internally."),
    "koc_l_kg_oc": ("L/kg organic carbon", "Organic-carbon-normalized partition coefficient; Kd=Koc*foc."),
    "organic_carbon_fraction": ("kg OC/kg dry sediment", "Bed organic carbon mass fraction, between zero and one."),
    "exchange_rate_s": ("s^-1", "Bed relaxation coefficient: J=k*(Kd*Cw*bed_dry_mass-Mbed)."),
    "bed_dry_mass_kg_m2": ("kg/m^2", "Active exchangeable bed dry solids per bed area; not contaminant mass."),
    "bed_degradation_rate_s": ("s^-1", "First-order parent transformation in exchangeable bed."),
    "reference_temperature_c": ("deg C", "Reference temperature of biodegradation, hydrolysis and bed rates."),
    "photolysis_reference": ("category", "natural_sunlight or artificial_irradiation; no automatic lamp-to-sunlight conversion."),
    "partition_mode": ("category", "kd or koc_foc; exactly one partition pathway is used."),
}
PARAMETER_DEFINITIONS = {}
for _key, _default in DEFAULT_PARAMETERS.items():
    if _key.endswith("_enabled"):
        _units, _description = "boolean", "Explicit process switch; enabled processes require their coefficients."
    elif _key.endswith("_theta"):
        _units, _description = "dimensionless", "Positive per-degree temperature multiplier; 1 disables correction."
    else:
        _units, _description = _DETAILS[_key]
    PARAMETER_DEFINITIONS[_key] = {
        "default": _default, "units": _units, "description": _description,
        "source_type": "user_required" if _default is None else "model_configuration",
    }


def default_parameters():
    return copy.deepcopy(DEFAULT_PARAMETERS)


def parameter_definitions():
    return copy.deepcopy(PARAMETER_DEFINITIONS)


def load_presets():
    with (Path(__file__).parent / "data" / "chemical_presets.json").open() as handle:
        return json.load(handle)


def load_preset(identifier):
    """Return independent metadata and a complete parameter dictionary."""
    catalog = load_presets()
    for item in catalog["presets"]:
        if item["id"] == identifier:
            result = copy.deepcopy(item)
            result["parameters"] = dict(default_parameters(), **result["parameters"])
            return result
    raise ValueError("Unknown chemical preset: {}".format(identifier))


def get_preset(identifier):
    """Alias shared with the biological fate module."""
    return load_preset(identifier)


def _array(value, name, shape, minimum=0.0, strict=False):
    if value is None:
        raise ValueError("{} is required for the enabled process".format(name))
    try:
        arr = np.broadcast_to(np.asarray(value, dtype=float), shape)
    except (TypeError, ValueError) as exc:
        raise ValueError("{} must be numeric and broadcast to {}".format(name, shape)) from exc
    if not np.all(np.isfinite(arr)):
        raise ValueError("{} must be finite".format(name))
    if minimum is not None and np.any(arr <= minimum if strict else arr < minimum):
        raise ValueError("{} must be {} {}".format(name, ">" if strict else ">=", minimum))
    return arr


def reaction_tendencies(water_mass, bed_mass, water_volume_m3, bed_area_m2,
                        parameters=None, environment=None):
    """Return per-cell tendencies in mg/s without modifying state or clipping rates.

    Environment keys: temperature_c, irradiance_ratio (mandatory for photolysis),
    light_reference (mandatory for photolysis), water_surface_area_m2 (mandatory
    for gas exchange), bed_dry_mass_kg_m2 and equilibrium_water_concentration_mg_m3
    (optional spatial overrides). All numeric inputs broadcast to the state shape.
    Integrator must preserve positivity; no dt is assumed here.
    """
    p = default_parameters()
    if parameters:
        unknown = set(parameters) - set(p)
        if unknown:
            raise ValueError("Unknown chemical parameters: {}".format(", ".join(sorted(unknown))))
        p.update(parameters)
    env = environment or {}
    try:
        mw, mb, vol, area = np.broadcast_arrays(
            np.asarray(water_mass, float), np.asarray(bed_mass, float),
            np.asarray(water_volume_m3, float), np.asarray(bed_area_m2, float))
    except (ValueError, TypeError) as exc:
        raise ValueError("Masses, volume and area must be broadcast-compatible numeric arrays") from exc
    shape = mw.shape
    mw = _array(mw, "water_mass", shape)
    mb = _array(mb, "bed_mass", shape)
    vol = _array(vol, "water_volume_m3", shape, strict=True)
    area = _array(area, "bed_area_m2", shape)
    for key, value in p.items():
        if key.endswith("_enabled") and not isinstance(value, (bool, np.bool_)):
            raise ValueError("{} must be boolean".format(key))
        if value is not None and key in _DETAILS and key not in (
                "photolysis_reference", "partition_mode", "reference_temperature_c"):
            _array(value, key, shape)
    for key in ("biodegradation_theta", "hydrolysis_theta", "bed_degradation_theta"):
        _array(p[key], key, shape, strict=True)
    reference_temp = _array(p["reference_temperature_c"], "reference_temperature_c", shape, minimum=None)
    if p["photolysis_reference"] not in ("natural_sunlight", "artificial_irradiation"):
        raise ValueError("photolysis_reference must be natural_sunlight or artificial_irradiation")
    if p["partition_mode"] not in ("kd", "koc_foc"):
        raise ValueError("partition_mode must be kd or koc_foc")
    if p["organic_carbon_fraction"] is not None and np.any(
            _array(p["organic_carbon_fraction"], "organic_carbon_fraction", shape) > 1):
        raise ValueError("organic_carbon_fraction must be <= 1")
    cw = mw / vol
    zero = np.zeros(shape, dtype=float)
    rates = {}
    for name, mass in (("biodegradation", mw), ("hydrolysis", mw), ("bed_degradation", mb)):
        rate = zero.copy()
        if p[name + "_enabled"]:
            coefficient = _array(p[name + "_rate_s"], name + "_rate_s", shape)
            theta = _array(p[name + "_theta"], name + "_theta", shape, strict=True)
            # Temperature is needed only when a correction was explicitly selected.
            if np.any(theta != 1):
                temp = _array(env.get("temperature_c"), "temperature_c", shape, minimum=None)
                with np.errstate(over="ignore", invalid="ignore"):
                    coefficient = coefficient * np.power(theta, temp - reference_temp)
            rate = coefficient * mass
        rates[name] = rate
    photo = zero.copy()
    if p["photolysis_enabled"]:
        if env.get("light_reference") != p["photolysis_reference"]:
            raise ValueError("light_reference must match photolysis_reference; no UV/lamp-to-sun conversion is assumed")
        photo = mw * _array(p["photolysis_rate_s"], "photolysis_rate_s", shape) * _array(
            env.get("irradiance_ratio"), "irradiance_ratio", shape)
    rates["photolysis"] = photo
    gas = zero.copy()
    if p["volatilization_enabled"]:
        velocity = _array(p["mass_transfer_velocity_m_s"], "mass_transfer_velocity_m_s", shape)
        surface = _array(env.get("water_surface_area_m2"), "water_surface_area_m2", shape)
        equilibrium = _array(env.get("equilibrium_water_concentration_mg_m3",
            p["equilibrium_water_concentration_mg_m3"]), "equilibrium_water_concentration_mg_m3", shape)
        gas = velocity * surface * (cw - equilibrium)
    exchange = zero.copy()
    if p["sorption_enabled"]:
        k = _array(p["exchange_rate_s"], "exchange_rate_s", shape)
        if p["partition_mode"] == "kd":
            kd = _array(p["kd_l_kg"], "kd_l_kg", shape) / 1000.0
        else:
            foc = _array(p["organic_carbon_fraction"], "organic_carbon_fraction", shape)
            kd = _array(p["koc_l_kg_oc"], "koc_l_kg_oc", shape) * foc / 1000.0
        dry_mass = _array(env.get("bed_dry_mass_kg_m2", p["bed_dry_mass_kg_m2"]),
                          "bed_dry_mass_kg_m2", shape) * area
        if np.any((dry_mass == 0) & (mb > 0)):
            raise ValueError("Sorption with nonzero bed contaminant requires positive active-bed dry solids")
        exchange = k * (kd * cw * dry_mass - mb)
    water_loss = rates["biodegradation"] + rates["hydrolysis"] + photo
    reaction_loss = water_loss + rates["bed_degradation"]
    result = {
        "water": -water_loss - gas - exchange,
        "bed": exchange - rates["bed_degradation"],
        "irreversible_loss": reaction_loss + np.maximum(gas, 0),
        "reaction_loss": reaction_loss,
        "atmospheric_export": np.maximum(gas, 0),
        "atmospheric_input": np.maximum(-gas, 0),
        "sorption_to_bed": exchange,
        "volatilization_net_export": gas,
    }
    result.update(rates)
    if any(not np.all(np.isfinite(value)) for value in result.values()):
        raise ValueError("Chemical tendencies overflowed; check coefficients and temperature correction")
    return result
