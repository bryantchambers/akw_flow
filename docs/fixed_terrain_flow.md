# Fixed-terrain flow MVP (version 2)

## Delivered scope

A separate 640 m square terrain-based 2D pilot at the northwestern Angkor Wat moat and mapped canal. It replaces feature-adjacency flow **for this pilot**, not the whole regional model. All supported land cells are included so overbank water has somewhere to go. Old regional models remain available for comparison. No erosion, breach development, organism-specific kinetics, or ancient-geometry claims.

Run with the GIS environment:

```sh
/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/build_terrain_flow.py
/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/restart_dashboard.py
```

Open `/channel-inspector`, select **New · fixed-terrain 2D pilot**, and click **Load / zoom to flow**. Scrub saved time through the rise and recession. Select current depth, water level, maximum depth, or unit tracer. Turn on terrain faces to inspect crest ranges and wetted widths. Orange lines are actual shared faces; arrows cross them in the direction of flow. A wetted face may carry zero net flow.

Parameters can be edited in `configs/terrain_flow.json` or in the dashboard's configuration editor and run button. Browser runs are limited to 10,000 cells, one day, and 200 saved intervals. A browser run replaces the local saved pilot result; restore the default using the command above. Original survey inputs are never modified.

## Geometry and numerical method

- Native georeferenced 0.5 m single-band DTM in EPSG:32648. Vertical metres remain provisional; datum, survey accuracy and bathymetric treatment need confirmation.
- Default 10 m computational grid; 32 equally weighted terrain quantiles per cell approximate subgrid hypsometry. Storage is the integral of positive water depth over these samples; its inverse provides stage. This is a compressed storage approximation, not exact native-pixel storage.
- Each face retains twenty 0.5 m strips. Each strip elevation is the maximum of the two adjacent native terrain pixels. Wet width and section area change with water level; several low strips can open separately. These are native face profiles, **not independently verified bank crests**.
- Local-inertial face momentum with pressure gradient, retained local acceleration and semi-implicit Manning friction. Hydraulic radius uses a wide-flow approximation. Advective momentum and detailed structure hydraulics are omitted. This is a custom prototype, not a certified implementation of LISFLOOD-FP or HEC-RAS.
- Adaptive gravity-wave CFL timestep and conservative donor-volume flux limiting. Signed flux supports backwater and reversal. Water and conservative tracer are transferred across the identical faces. Dry-cell volume is nonnegative; residual tracer mass is retained if a cell becomes dry.
- Mapped water determines initial wetting and selection of inflow boundary cells, **not adjacency or a permanent wet-area mask**. No blanket incision or sink filling.
- Default hypothetical north-boundary stage rises 1.5 m over 300 s, remains high to 600 s, and recedes by 900 s. Initial level derives from the 25th percentile of mapped-water terrain plus 0.15 m. This initialization is an experiment, not observed hydrology. Other perimeter faces are closed.

## Fixed scenario controls

`terrain_modifications` supports projected GeoJSON polygons with `mode` of `set`, `lower`, or `raise`, an absolute `elevation_m`, and mandatory `evidence` text. These modify only the in-memory scenario surface and its storage/face geometry. Use for explicit uncertain bed or bank reconstructions; there is no automatic burning of mapped channels.

`face_controls` supports `face_index`, `profile_elevations_m` (one absolute elevation per native face strip: twenty at 10 m spacing), and `evidence`. It overrides that face profile without changing cell storage. A high profile can represent a fixed barrier; lower strips represent fixed openings. Indices depend on extent, spacing and no-data support: reconcile controls whenever the grid changes. These are terrain-face controls, **not culvert, gate or calibrated weir equations**.

Uniform rainfall and capacity-limited infiltration over the estimated wetted fraction are optional. Infiltration removes water and dissolved unit tracer; no soil tracer storage is simulated. Optional groundwater is a fixed external head with per-cell conductance, not the existing finite-storage aquifer module. Porosity and permeability do not independently determine this conductance without a chosen geometry. Groundwater inflow and rainfall carry zero unit tracer. The default disables all three processes.

## Transport and interpretation

A conservative dimensionless tracer enters selected stage boundary cells at concentration 1; initial concentration is zero. It tests routing and retention without pathogen survival assumptions. Upwind advection is numerically diffusive. Physical dispersion, sediment-associated transport, reactions, microbial parameters, and existing fate-model coupling are **not yet implemented in this new solver**. Concentration and depth maps are not validated contaminant or bacterial hotspot predictions. Maximum depth is inundation history, not hotspot likelihood or measured bathymetry.

## Acceptance and remaining gates

Synthetic tests cover irregular-bed lake-at-rest, storage inversion, dry receiving cells, containment below bank crest, progressive face widening, multiple outlets, reversal during recession, water/tracer budgets, and rainfall/infiltration/fixed-head exchange. The real pilot closes water and tracer budgets to numerical precision. These checks establish implementation properties; they do not validate site hydrology.

Before regional rollout or hotspot claims:

1. Inspect native crest and cross-section profiles with the source features. A barrier inside a coarse cell can be missed by its boundary faces. Align/refine the mesh or add documented controls; do not infer safety from budget closure.
2. Confirm source vertical metadata and bathymetry; define scenario bed geometry where water obscures the bed.
3. Review inlet/outlet locations and forcing. Closed crop boundaries are artificial and cannot represent the regional catchment.
4. Run spatial refinement and validate overtopping/outlet discharge against an established solver or benchmark. Temporal checks alone are insufficient. Quantile storage cannot resolve separate disconnected pools inside a cell.
5. Delineate the contributing watershed with broader terrain; prepare rainfall/inflow and downstream boundary scenarios.
6. Add appropriately validated dispersion and transport coupling, then compare retention across geometry/forcing ensembles.

A coupled 1D reach / 2D waterbody system remains a possible regional extension. This delivery deliberately uses 2D terrain cells throughout the pilot; it does not yet extract a surveyed reach network or produce a complete regional watershed.

## Provenance and references

Private outputs are under `assets/private/terrain_flow/`: `terrain_flow.json` (dashboard), `mesh.json` (numerical geometry), and `manifest.json` (parameters, source file state, code hashes, boundaries and budgets). Only the named dashboard result is served; raw input and mesh paths remain blocked. Source inputs and derivatives remain gitignored.

- Bates, Horritt & Fewtrell (2010), local-inertial modelling rationale: https://doi.org/10.1016/j.jhydrol.2010.03.027
- USACE, terrain-based storage/face properties and bank-aligned mesh guidance: https://www.hec.usace.army.mil/confluence/rasdocs/rasum/6.6/entering-and-editing-geometric-data/2d-flow-areas
- USGS, targeted hydrologic enforcement: https://www.usgs.gov/publications/hydrologic-enforcement-lidar-dems

These sources inform the design; they do not validate this custom numerical implementation.

## Verification snapshot (10 November 2026)

77 unit tests passed, including nine new terrain acceptance tests. Halving the real pilot maximum timestep from 1 s to 0.5 s changed final mean cell depth by RMSE 0.0000138 m and maximum absolute difference 0.000255 m. This is a temporal sensitivity check, not spatial convergence or site validation. Desktop loading, time scrubbing and tracer display were checked in Chromium.

## Spatial sensitivity follow-up

A matched 10 m / 5 m comparison and native-terrain screening are now available. See [the bank and mesh review](terrain_refinement_review.md) for results, changed initialization/inlet selection, and acceptance limits. This adds review evidence, not a bank-aligned regional model.
