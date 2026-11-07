# Configurable environmental chemical transport

This module supplies local reaction and bed-exchange tendencies to the shared
finite-volume hydraulic solver. It is an exploratory, single-parent-chemical
screening calculation, not an implementation or validation of EPA WASP. It can
represent contaminant retention under canal blockage, altered residence time or
changing water volumes only to the extent those conditions are supplied by the
hydraulic model. A bed concentration hotspot and a dissolved-water hotspot are
different outputs. Neither is a calibrated ecological risk estimate.

## State and equations

Each wet compartment stores dissolved-parent mass `Mw` and exchangeable-bed
parent mass `Mb` in mg. `V` is water volume (m³), `Ab` bed area (m²), and
`Cw = Mw/V` (mg/m³). Display conversion: `mg/L = Cw/1000`.
Bed concentration can be reported in mg/kg dry solids using `Mb/S`, where
`S = Ab * bed_dry_mass_kg_m2`. Bed contaminant mass is not bed dry solids.
Zero/negative water volumes are rejected; dry cells require a separate hydraulic
drying/rewetting policy rather than a small invented replacement volume.

The shared routing solver adds conservative advection, longitudinal dispersion,
molecular diffusion, junction mixing, and source loading. In a reach this
corresponds to `d(A*C)/dt + d(Q*C)/dx = d(A*D*dC/dx)/dx + reaction + loading`,
with changing water volume accounted for by the hydraulic water balance.
This module does not duplicate those transport terms.

For first-order biodegradation, hydrolysis and bed transformation, users supply
condition-specific reference rates in s⁻¹ and optional temperature corrections:

```
k(T) = k_ref * theta ** (T - T_ref)
Lbio = kbio(T) * Mw
Lhyd = khyd(T) * Mw
Lbed = kbed(T) * Mb
Lphoto = kphoto_ref * irradiance_ratio * Mw
```

`theta=1` disables temperature correction; it is a configuration choice, not a
chemical property estimate. A half-life in days can be converted by
`k = ln(2)/(half_life_days*86400)` only for the conditions of that measurement.
No half-life or Q10 is presumed universal. Hydrolysis is an effective supplied
rate: acid/base catalysis, pH and speciation are not inferred.

Photolysis requires matching `photolysis_reference` and environment
`light_reference`: either `natural_sunlight` or `artificial_irradiation`.
`irradiance_ratio` is an effective depth-averaged, spectrum-appropriate multiplier
relative to the reference rate. The caller must incorporate shading, turbidity,
water depth, season and sensitizers. A ratio of zero represents darkness.
Lamp irradiance or treatment UV dose must not be passed off as natural sunlight.

Air/water exchange uses an externally specified overall water-equivalent
transfer velocity and water surface area:

```
Jair = k_transfer * A_surface * (Cw - C_equilibrium)
```

Positive `Jair` is export; negative is atmospheric uptake. The equilibrium water
concentration may be supplied directly from observed air concentration and a
consistent Henry partition calculation. This implementation does not infer it
from vapor pressure or an ambiguous Henry constant. Clean air (`C_equilibrium=0`)
is an explicit editable default. A gas transfer coefficient is not a molecular
diffusion coefficient and includes any required air-side resistance externally.

Reversible bed partition is a kinetic relaxation toward a linear equilibrium
target, with exactly one selected parameterization:

```
Kd = kd_l_kg / 1000                         # m³/kg
or Kd = koc_l_kg_oc * organic_carbon_fraction / 1000
Jbed = exchange_rate_s * (Kd * Cw * S - Mb)  # mg/s
dMw/dt = -Lbio - Lhyd - Lphoto - Jair - Jbed
dMb/dt = Jbed - Lbed
```

This is not instantaneous equilibrium. At equilibrium `Mb/S = Kd*Cw`.
The water-to-bed rate coefficient is `exchange_rate_s*Kd*S/V`, whereas the
desorption coefficient is `exchange_rate_s`. Do not add an independent sorption
sink, an instantaneous equilibrium allocation or a second settling transfer for
the same mass. No suspended-solid chemical state, particle settling,
resuspension, burial, bed erosion or porewater diffusion is represented here.
Those need explicit solid states and a solids mass balance before implementation.

The returned `irreversible_loss` is **loss of parent mass from the modeled
water-plus-bed system**, equal to transformation plus positive atmospheric
export; it does not mean mineralization or destruction. Products are untracked,
and atmospheric export is not chemical destruction. The separate diagnostics
are `reaction_loss`, `atmospheric_export`, and `atmospheric_input`.
The local ledger is exactly:

```
d(Mw+Mb)/dt = atmospheric_input - irreversible_loss
```

Sorption cancels algebraically. Parent transformation products, elemental
conservation and transformation toxicity require additional species states,
stoichiometric/molar yields and validation; this version makes no product claims.

## API and integration

`reaction_tendencies(water_mass, bed_mass, water_volume_m3, bed_area_m2,
parameters, environment)` returns numpy arrays broadcast to the input state
shape. Scalars can configure a whole network; array-valued numeric parameters
allow compartment-specific conditions. Inputs and output rates are finite;
positive volume, nonnegative masses/areas/rates, boolean switches, and fractional
organic carbon in `[0,1]` are enforced. Unknown parameter keys raise an error.
All processes default to explicitly disabled. Required kinetic coefficients
default to `null`; enabling a process without them raises a descriptive error.

`default_parameters()` and `parameter_definitions()` return independent copies.
`load_presets()` returns the JSON catalog; `load_preset(id)` returns metadata
and merged full parameters. Presets retain provenance and missing-site-input
lists. Scalar/array environment keys are `temperature_c`, `irradiance_ratio`,
`light_reference`, `water_surface_area_m2`, and optional spatial overrides for
`bed_dry_mass_kg_m2` and `equilibrium_water_concentration_mg_m3`.

Rates are tendencies, not a time step: **the caller must prevent negative mass**.
Explicit Euler requires a step bounded by the sum of all outgoing process
coefficients for each state, in addition to hydraulic CFL/dispersion bounds.
For bed exchange include `kexchange*Kd*S/V` for water and `kexchange` for bed.
Use substepping, an exact linear reaction solve or a positivity-preserving
integrator. Do not silently clip negative mass, which breaks conservation.
Transfer stiffness can increase sharply when a reach becomes shallow.

## EPA evidence and parameter provenance

Sources checked 2026-11-06:

- [EPA WASP](https://www.epa.gov/hydrowq/water-quality-analysis-simulation-program-wasp)
  supports surface-water pollutant modeling and linkage with hydrodynamic and
  watershed models. Its supported pollutant types include nutrients, organic
  chemicals and metals. The implementation here uses standard screening mass
  balances; EPA has not endorsed or validated this repository.
- [EPA EPI Suite](https://www.epa.gov/tsca-screening-tools/epi-suitetm-estimation-program-interface)
  provides screening property/fate estimates. EPA advises using acceptable
  measured properties when available. WVOLWIN estimates use assumed river/lake
  depth and wind conditions; these assumptions must be replaced or documented
  for Angkor rather than importing a universal volatilization half-life.
- [EPA CompTox property guidance](https://www.epa.gov/comptox-tools/comptox-chemicals-dashboard-about)
  and the [Dashboard](https://comptox.epa.gov/dashboard/) supply reported and
  predicted properties. Export individual property details and preserve identity,
  source study, method, environmental conditions, units, uncertainty, model and
  version. A prediction is not a measurement. No automatic CompTox record ingest
  or EPI execution is implemented; the catalog records only actually reviewed data.
- [EPA ECOTOX](https://www.epa.gov/comptox-tools/ecotoxicology-ecotox-knowledgebase-resource-hub)
  supplies ecological effects data. It is useful later for comparing exposure
  predictions with appropriate species/endpoints; effect thresholds are not
  chemical degradation or partition coefficients.
- [EPA historical EXAMS overview](https://www.epa.gov/sites/default/files/2017-09/documents/ee-0108_1-4_acc.pdf)
  describes organic-chemical screening with environmental, chemical and loading
  inputs, including pseudo-first-order transformations. This module is not an
  EXAMS compatibility layer.
- The [EPA legacy atrazine factsheet](https://archive.epa.gov/water/archive/web/pdf/archived-technical-fact-sheet-on-atrazine.pdf),
  PDF pages 2–3, reports mean `Koc=122` for four soils. The property seed is labeled
  an EPA-reported experimental summary, not an Angkor sediment measurement.
  Its conditional laboratory photolysis findings do not supply natural-light
  defaults. Atrazine remains an uncalibrated, hypothetical modern example.

The chloride approximation is an idealized conservative tracer configuration.
The user-defined template is incomplete until local conditions and measured
rates, or explicitly labeled predictions with sensitivity bounds, are supplied.
For each new parameter record original source URL/study, units, phase, pH,
temperature, light spectrum, redox condition, measured/estimated status, and
uncertainty or justified range. Calibrate against independent water and sediment
observations and reserve observations for validation.

## Scope before scientific interpretation

No automatic speciation, pH dynamics, ionic strength, dissolved oxygen, redox,
DOC/colloid binding, solubility/precipitation, metal complexation, bioaccumulation,
suspended solids, reaction products or feedback on hydraulics is represented.
The water state is dissolved chemical; it must not be interpreted as total
unfiltered concentration when particle transport matters. Nitrate/ammonium
presets are deliberately absent: coupled nitrification, denitrification,
oxygen demand, temperature, organic carbon, redox and uptake are necessary for
defensible nutrient transformations, rather than a universal decay coefficient.
Use EPA WASP with an appropriate kinetics module and calibrated hydraulic
linkage when these coupled processes determine the question. High-resolution
terrain improves geometry but does not resolve these missing chemical inputs.
