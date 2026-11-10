# Regional native-resolution flow model

## Coverage and resolution

Open `/regional-terrain` from the dashboard's **Regional flow · 0.5 m** link.

This version uses the complete supplied Huma-Num terrain footprint at **actual 0.5 m hydraulic spacing**, with no coarsening or subgrid quantiles:

- Raster dimensions: 12,032 rows × 30,948 columns.
- Total grid cells: 372,366,336.
- Valid terrain cells: 372,327,658; valid area 93.0819 km².
- Projected CRS: EPSG:32648. Original source vertical units, datum and accuracy remain unverified.
- Coverage means the entire **available survey rectangle**, not all Greater Angkor. Additional 0.5 m data is needed outside the outlined footprint.

The numerical domain is continuous. Raster/display tiles do not impose internal hydraulic boundaries. Neighbouring native cells exchange signed water and tracer fluxes across their actual shared faces. A high intervening bed or bank blocks a face until water overtops its elevation. The graph is implicit in the raster faces; we do not generate hundreds of millions of GeoJSON lines or invent feature-anchor connections.

The prior pilot and refinement views are preserved.

## Viewing

- Toggle satellite imagery, native hillshade or elevation colours, and mapped water features independently.
- Adjust terrain/output transparency.
- Zoom in to see native terrain detail. Hillshade is useful for inspecting bank and ditch relief; it is a display derivative, not a terrain modification.
- Click to read an actual native cell: bed elevation, depth, stage, east/south face discharge, and unit tracer.
- Initial and final saved states are separate choices. The final state becomes available automatically after export. There is no invented interpolation or animation between them.
- Optional arrows sample the final face-velocity fields across the viewport. Glyph length is a display choice; they are not streamlines or particles. Exact discharges remain available at native-cell clicks.
- Tile rasters use nearest-neighbour display samples. At regional zoom, small wet patches can be undersampled; mapped outlines and zooming help. This changes display detail, not the model spacing. The UI reports approximate metres per screen pixel.
- Depth colours cover 0–1 m with square-root scaling; values below 1 mm are hidden. Exact values are retained in the rasters and point inspector. Elevation colours clip to 15–60 m.

## Scenario, not a forecast

The supplied configuration is a **30-second startup acceptance check**, using hypothetical low-water levels and 30 mm/hour rainfall. It does not represent a calibrated flood, drought, historical episode or contaminant source.

Each four-connected mapped water component receives an initial level equal to its minimum native DTM elevation plus 0.10 m. Only pixels below that level start wet; higher parts remain dry. This creates very low-water starting conditions, not a representation of the full modern mapped water extent. A connected mapped polygon can contain hydraulically separated basins; the initialization is therefore explicitly provisional. Source polygons and buffered mapped water traces guide initialization only, never determine permanent hydraulic connections.

Uniform depth on sloping mapped water was rejected as a regional default because it creates artificial initial water-surface gradients. Future scenarios need reviewed, spatially appropriate starting water levels, actual inflows/outflows, and reconstructed bathymetry where justified. Changing the level offset is an experiment, not calibration.

The outer survey boundary and no-data cells are closed. Regional groundwater and prescribed stage boundary forcing are not yet supported by this native engine; unsupported requests are rejected. Uniform rainfall and water-limited infiltration are configurable. Infiltration exports dissolved unit tracer; no soil tracer compartment or aquifer is simulated. No erosion, evolving banks, sediment or breach formation is included.

## Numerical method

`hydraulics/native_grid.py` implements a compiled, multithreaded local-inertial raster approximation:

1. Update east/south unit-width face discharges using local acceleration, water-surface gradients and fully implicit quadratic Manning friction.
The friction step solves the nonlinear quadratic resistance implicitly, including newly wetted faces.

2. Compute donor-volume limits using all four faces of each cell.
3. Apply one shared discharge per face; use identical opposite-signed exchanges in the two neighbours.
4. Update water and upwind conservative unit-tracer mass; apply rainfall and bounded infiltration.

A gravity-wave CFL constraint limits the timestep. Dry-face cutoff and wetting/drying are explicit. The wide-flow resistance approximation omits advective momentum and detailed structure equations. Native spacing resolves more terrain features but does not establish validity for steep, rapidly varying or supercritical flows. This is a custom research solver, not an independently validated implementation of HEC-RAS or LISFLOOD-FP.

State and conservation sums use float64; terrain is the source float32. Exported raster fields are float32. Face velocities are computed using water depth at the face, rather than dividing a face discharge by a nearly dry cell's depth. Output tiling has no role in flux calculations.

Unit tracer starts at concentration 1 in initially wet mapped-water cells; rainfall adds zero tracer. This is a routing/conservation check. No bacterial species parameters, inactivation, chemical reactions, physical dispersion, sorption or validated hotspot interpretation are included.

## Build and resources

Install the optional compiled solver/viewer dependencies alongside the GIS environment:

```sh
python3.12 -m pip install -r scripts/requirements-gis.txt -r scripts/requirements-native.txt
NUMBA_NUM_THREADS=40 /maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/build_regional_native.py
/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/restart_dashboard.py
```

Configuration: `configs/regional_native.json`. Optional `terrain_modifications` use projected GeoJSON polygons, `mode` (`set`, `lower`, `raise`), absolute `elevation_m`, and mandatory `evidence`. They alter only the in-memory scenario terrain and its cache, preserving source no-data and native alignment. Optional `initial_water_levels` use projected polygons, absolute `stage_m`, mandatory `evidence`, and `mapped_water_only` (default true). They override low-water initialization locally. Both lists are empty in the delivered run. Edits remain fixed throughout the simulation; none represent erosion.

`initial_mapped_water_depth_m` acts as a **level offset above the minimum elevation of each mapped component**, not a uniform water depth throughout that polygon. Configuration:  `NUMBA_NUM_THREADS` sets an upper bound; the requested thread count must not exceed it. The engine accepts 1–40 threads. The current corrected run uses 32 to preserve in-flight work; subsequent launches default to 40. Measured resident memory is approximately 26 GB. Each timestep takes several wall-clock seconds on this host. A 30-second startup run takes minutes, not 30 wall-clock seconds. Longer flood/drought scenarios require resource planning, reviewed forcing and further solver validation.

Build progress is written atomically to `assets/private/regional_native/progress.json` and shown in the viewer. A PID lock prevents overlapping regional builds. To stop a build, signal that recorded process after confirming its command; a normal interrupt releases the lock. There is no timestep restart/checkpoint support yet; interruption requires rerunning the numerical scenario. The tiled terrain cache can be reused when source size and modification time match. After an abnormal kill, verify that the recorded PID is no longer a build process before removing a stale lock.

Private artifacts:

| File | Contents |
|---|---|
| `terrain.tif` | Native scenario terrain (source plus any explicit fixed edits); no resampling |
| `initial.tif` | Native initial water depth |
| `final.tif` | Native depth, east/south unit-width flux, unit tracer and east/south face velocity |
| `manifest.json` | Coverage, resolution, configuration, source state, code hashes, budgets and run history |
| `progress.json` | Current build stage and numerical progress |

Original surveys are never modified. All spatial inputs and outputs remain ignored by Git. HTTP serves only allowlisted raster tiles, cell samples, vector samples and status metadata; direct private raster downloads remain blocked.

## Acceptance and next gates

Synthetic checks include lake-at-rest over uneven bed, bank containment, wetting/drying, no-data barriers, rain/infiltration budgets, rotational symmetry, and agreement with the existing face solver on a native-cell chain. Viewer checks include actual cell reads, velocity-band sampling, tile generation and path validation. Passing these checks is not site validation.

Before using this regional version to infer hotspot locations:

- Confirm vertical metadata and the DTM's treatment of standing water and submerged beds.
- Review starting levels, banks, openings and externally forced catchment connections.
- Compare outlet discharges and inundation against observations or an established solver.
- Run physically relevant, sufficiently long forcing scenarios and test numerical sensitivity.
- Add and validate the intended dispersion and fate processes before interpreting concentrations.

References informing the method and resolution distinction:

- Bates, Horritt & Fewtrell (2010): https://doi.org/10.1016/j.jhydrol.2010.03.027
- USACE grid-size and timestep guidance: https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.3/running-a-model-with-2d-flow-areas/selecting-an-appropriate-grid-size-and-time-step

These references do not validate this implementation.

## Additional numerical check

A uniform wide-sheet, constant-slope benchmark compares interior unit-width discharge against the analytic local-inertial solution `q(t) = q_eq tanh(t/tau)`. At 0.5 m spacing, 0.1 m depth, slope 0.0001, Manning n 0.05 and 100 s, computed mean discharge differs by about 0.00179% at a 0.01 s timestep. Boundaries are far enough away to avoid affecting the sampled interior. This checks that specific friction/acceleration regime; it does not validate arbitrary regional flood hydraulics.

Executed builder/solver source snapshots for the delivered run are retained locally under `assets/private/regional_native/code_snapshots/`, keyed by the hashes recorded in its manifest. Later optional configuration additions do not change the recorded run.

## Friction and velocity audit

The first full-region startup trial conserved water and tracer but exhibited implausible shallow-film velocity diagnostics. It was archived privately and withdrawn from the current viewer. The revised engine solves nonlinear quadratic Manning friction fully implicitly and computes face velocities using the same predictor-depth geometry used for its final discharge update. The revised code passed the synthetic tests and 30-second terrain-patch checks before the regional rerun. Regime limitations of the local-inertial approximation still apply; conservation alone does not validate a flow field.

Further method context: https://www.jstage.jst.go.jp/article/hrl/13/2/13_28/_article/-char/en and https://doi.org/10.1002/wrcr.20366 . These sources motivate numerical and regime checks; they do not certify this implementation.

## Completed native run and export audit

The corrected 30-second run completed on 372,327,658 valid 0.5 m cells using 32 threads and 300 timesteps. Total build/export/display-pyramid wall time was approximately 16.4 minutes. Longer or deeper flood scenarios may need much more computation; this timing is not a forecast-run throughput guarantee. Subsequent launches default to the user-authorized maximum of 40 threads.

Water residual: -8e-11 m³; unit-tracer residual: -4.73e-11. Float32 export volume differs from the solver sum by 4.75e-07 m³. Sixteen sampled source/cache windows matched native source data. Recorded executed-source snapshots were verified.

The corrected maximum exported face velocity is 0.826 m/s. There are 85 faces exceeding Froude 1 at face depths of at least 1 cm. Many thinner films also exceed that regime. Those locations require review; the local-inertial approximation is not a validated prediction there. The startup case does not establish hotspot locations or regional flood/drought accuracy.

Hillshade is now computed at native 0.5 m spacing with a halo across storage blocks, then resampled for display. It does not recompute slope from enlarged screen pixels. The durable Miniforge environment and browser views were checked after migration; the retired temporary environment was removed only after its calculation/export process ended.
