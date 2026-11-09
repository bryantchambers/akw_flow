# Mapped-water flow pilot and optional groundwater

The inspector's Flow scenario panel loads the pilot model, shows saved times and adjustable simulated-depth transparency, and accepts edited JSON parameters. `python scripts/build_humanum_flow.py` rebuilds from `configs/humanum_flow.json`. Outputs remain private. This first mapped-water model covers only the existing 256 m pilot, not the complete feature inventory or either baray.

The 0.5 m source terrain is rasterized against mapped Canal, Water, Pond and Temple Moat geometry, then aggregated to configurable 8 m storage cells. A cell's area is its mapped wet footprint. Shared-interface wet pixels determine candidate surface connections and widths; no dry gap is automatically bridged. Disconnected subcell water areas may still be conflated at this resolution. Raised features, pond banks, gates and culverts need explicit review; they are not assigned barrier elevations here.

Cell bed proxies use the 20th percentile of present terrain inside mapped water minus an editable assumed incision (default 0.5 m). Initial depth (0.3 m), Manning n (0.035) and all soil values are hypothetical, not local measurements. Elevation units are provisionally metres; vertical datum and bathymetry remain unresolved. Edit grid resolution, incision, initial depth, roughness, rainfall, explicit node inflows/outflows, node bed offsets and edge overrides. Default surface boundaries are closed, so the demonstration is redistribution/relaxation of initial storage, not a simulated observed flood.

## Groundwater component

Groundwater defaults disabled. `groundwater.enabled=true` activates saturated, unconfined lumped columns underneath model water cells. It is NOT a continuous regional aquifer, unsaturated infiltration, Richards flow or a reconstruction of Angkor groundwater. Lateral groundwater connections currently follow the surface grid links; subsurface pathways beneath unmapped land are absent. No pumping, evapotranspiration or chemical/microbial groundwater transport is included.

- Porosity `n` is total pore fraction; `specific_yield` Sy is drainable storage, with 0 < Sy <= n <= 1. Changing porosity alone does not determine hydraulic conductivity.
- Choose `conductivity_mode`: hydraulic conductivity K [m/s], or intrinsic permeability k [m²] converted through K=k rho g/mu using explicit density and dynamic viscosity. Only the selected mode controls lateral aquifer conductivity.
- Bed exchange has its own `bed_hydraulic_conductivity_m_s` and `bed_thickness_m`. Leakage Q=(Kbed Abed / thickness)(surface head - groundwater head), with dry-surface leakage disabled. It is an effective saturated connection; unsaturated bed drying/clogging is not represented.
- Groundwater drainable storage G=Sy Acolumn (head - aquifer base). This is drainable storage above the chosen base, not total pore water. `column_area_m2` is independent of partial wet surface area; change it when changing grid scale (default 64 m² for 8 m grid).
- Lateral Darcy flux uses harmonic-mean K, minimum saturated thickness, link width and head gradient. Widths currently follow mapped interface widths; geology may require different connectivity/sections.
- All heads share the same provisional vertical reference. Set aquifer base depth, initial head relative to the assumed bed, column area and soil values explicitly. Return seepage is allowed; there is no hard cap on water-table elevation, so flooded/pressurized behavior needs further review.
- Positive-state adaptive timesteps and separate surface/groundwater budgets track exchange once. Combined conservation is reported alongside surface-only conservation. Time-scale convergence remains necessary for quantitative work.

Surface-only transport coupling explicitly rejects groundwater-enabled hydraulic outputs until solute exchange between compartments is implemented; it does not silently lose biological/chemical mass into seepage.

## References

General methodological references, not sources of Angkor soil calibration:
- Alley, Reilly & Franke (1999), *Sustainability of Ground-Water Resources*, USGS Circular 1186. https://doi.org/10.3133/cir1186
- Focazio et al. (2002), *Assessing Ground-Water Vulnerability to Contamination*, USGS Circular 1224. https://doi.org/10.3133/cir1224
- USACE (1999), *Groundwater Hydrology*, EM 1110-2-1421. https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-2-1421.pdf

Official PDF downloads returned HTTP403 on 2026-11-09; library entries retain external source links and mark local copies unavailable. Governing choices above are implementation assumptions informed by general Darcy/storage concepts, not implementations validated by those publications.

## Inspection layer order and network view

Explicit Leaflet panes keep imagery below terrain, terrain below mapped features, and simulated depth and network links above both. The toolbar's Load / zoom to flow fits the bounded pilot rather than leaving it invisible in a regional overview. Network view hides background layers and shows the pilot's 393 storage nodes and 631 candidate links in geographic layout; Layered view restores chosen backgrounds. This is the computational pilot graph, not a reconstructed complete ancient-city network. Time controls update the same graph's discharge and depth values. Explicit panes preserve ordering after terrain changes and layer toggles.
